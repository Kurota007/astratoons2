import os, io, json, logging, zipfile, shutil, requests
from PIL import Image as PillowImage
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import F, OuterRef, Subquery, Value, CharField, DateTimeField
from django.http import Http404, JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import operator
from datetime import timedelta

# Importações do REST Framework
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics

from taggit.models import Tag
from wagtail.images.models import Image as WagtailImage
from wagtail.models import Page, Locale
from wagtail.contrib.settings.models import BaseSiteSetting

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

try: from novels.models import NovelPage, NovelChapterPage
except ImportError: NovelPage = None
try: from subscriptions.models import AssinaturaUsuario 
except ImportError: AssinaturaUsuario = None
try: from core.models import GlobalSettings 
except ImportError: GlobalSettings = None

from .forms import MangaCommentForm 
from .models import MangaPage, MangaChapterPage, Favorite, ChapterImage, MangaComment, MangaStatus, ReadingHistory
from .serializers import MangaListSerializer
from comments.models import Notification
from .utils import process_manga_zip

logger = logging.getLogger(__name__)


# ==============================================================================
# VIEWS DA API PARA O APLICATIVO MÓVEL
# ==============================================================================

class TesteAPIView(APIView):
    """
    Uma view de teste simples que não requer autenticação.
    Acessível via GET em /api/manga/teste/
    """
    permission_classes = [AllowAny]

    def get(self, request):
        dados = { 'mensagem': 'A API está funcionando!' }
        return Response(dados)


class MangaListAPIView(generics.ListAPIView):
    """
    Lista todos os objetos MangaPage que estão publicados e visíveis.
    Usa o tradutor MangaListSerializer para formatar os dados.
    Acessível via GET em /api/manga/lista/
    """
    serializer_class = MangaListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return MangaPage.objects.live().public().order_by('title')


# ==============================================================================
# Views do Site
# ==============================================================================

@login_required
@require_POST
def toggle_favorite_view(request):
    if request.content_type != 'application/json':
        return JsonResponse({'status': 'error', 'message': 'Tipo de conteúdo inválido.'}, status=415)
    
    try:
        data = json.loads(request.body)
        manga_id = data.get('manga_id')
        if manga_id is None:
            return JsonResponse({'status': 'error', 'message': '"manga_id" não encontrado.'}, status=400)
        manga_id = int(manga_id)
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Dado inválido para "manga_id".'}, status=400)

    try:
        manga_page = MangaPage.objects.live().public().get(pk=manga_id)
    except MangaPage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Mangá não encontrado.'}, status=404)
    except MangaPage.MultipleObjectsReturned:
        logger.error(f"Múltiplos MangaPage ID {manga_id}")
        return JsonResponse({'status': 'error', 'message': 'Erro interno (ID duplicado).'}, status=500)

    favorite_instance, created = Favorite.objects.get_or_create(user=request.user, manga=manga_page)
    
    action_to_bot = None
    if created:
        action_taken = 'added'
        is_favorited_final_state = True
        action_to_bot = 'add_role'
        logger.info(f"User '{request.user.username}' FAVORITOU Manga '{manga_page.title}'.")
    else:
        favorite_instance.delete()
        action_taken = 'removed'
        is_favorited_final_state = False
        action_to_bot = 'remove_role'
        logger.info(f"User '{request.user.username}' DESFAVORITOU Manga '{manga_page.title}'.")

    try:
        discord_id = request.user.profile.discord_id 
    except AttributeError:
        discord_id = None
        logger.warning(f"Usuário {request.user.username} não tem 'profile.discord_id' para notificar o bot. Ação no site concluída.")

    if discord_id:
        bot_api_url = os.getenv('DISCORD_BOT_API_URL')
        bot_secret = os.getenv('DISCORD_BOT_SECRET_TOKEN')
        role_id = os.getenv('DISCORD_FAVORITE_ROLE_ID')

        if not all([bot_api_url, bot_secret, role_id]):
            logger.error("ERRO CRÍTICO: Variáveis de ambiente da API do bot não carregadas pelo Django/Gunicorn.")
        else:
            headers = {'Authorization': f'Bearer {bot_secret}', 'Content-Type': 'application/json'}
            payload = {'user_id': str(discord_id), 'role_id': str(role_id), 'action': action_to_bot}
            
            try:
                response = requests.post(bot_api_url, json=payload, headers=headers, timeout=5)
                if response.status_code == 200:
                    logger.info(f"Bot notificado com SUCESSO. Ação: {action_to_bot} para user {discord_id}.")
                else:
                    logger.error(f"O Bot retornou um ERRO. Status: {response.status_code}, Resposta do Bot: {response.text}")
            except requests.exceptions.RequestException as e:
                logger.error(f"FALHA DE CONEXÃO ao notificar o bot do Discord: {e}")

    return JsonResponse({'status': 'success', 'action': action_taken, 'is_favorited': is_favorited_final_state, 'manga_id': manga_page.id})

@login_required
def download_chapter_zip_view(request, manga_slug, chapter_number):
    user_is_vip = hasattr(request.user, 'assinatura_vip') and request.user.assinatura_vip.esta_ativa
    if not (request.user.is_staff or user_is_vip):
        messages.error(request, "Apenas assinantes VIP podem fazer o download de capítulos.")
        return redirect('subscriptions:plans')
    try:
        manga = get_object_or_404(MangaPage, slug=manga_slug)
        chapter = get_object_or_404(MangaChapterPage.objects.child_of(manga), chapter_number=chapter_number)
    except Http404:
        logger.warning(f"Download falhou: Capítulo não encontrado para manga_slug='{manga_slug}' e chapter_number='{chapter_number}'")
        messages.error(request, "Capítulo não encontrado.")
        try:
            manga_page_for_redirect = MangaPage.objects.get(slug=manga_slug)
            return redirect(manga_page_for_redirect.get_url())
        except MangaPage.DoesNotExist:
            return redirect('/')
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        first_image_instance = chapter.chapter_images.order_by('sort_order').first()
        if not first_image_instance:
            messages.error(request, "Este capítulo não contém imagens para download.")
            return redirect(chapter.get_url())

        chapter_image_directory = os.path.dirname(first_image_instance.encrypted_file.path)
        
        try:
            avif_files = sorted([f for f in os.listdir(chapter_image_directory) if f.lower().endswith('.avif')])
            if not avif_files:
                raise FileNotFoundError
        except (FileNotFoundError, AttributeError):
            messages.error(request, "Este capítulo não contém imagens (AVIF) para download.")
            return redirect(chapter.get_url())

        for avif_filename in avif_files:
            file_path = os.path.join(chapter_image_directory, avif_filename)
            zipf.write(file_path, arcname=avif_filename)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    safe_manga_title = slugify(manga.title)
    safe_chapter_number = slugify(chapter.chapter_number)
    response['Content-Disposition'] = f'attachment; filename="{safe_manga_title}-capitulo-{safe_chapter_number}.zip"'
    return response

def chapter_reader_view(request, manga_slug, chapter_slug):
    try:
        manga = get_object_or_404(MangaPage.objects.live().public(), slug=manga_slug)
        current_chapter = get_object_or_404(MangaChapterPage.objects.live().public().child_of(manga), slug=chapter_slug)
    except Http404:
        logger.warning(f"Conteúdo não encontrado para manga_slug='{manga_slug}', chapter_slug='{chapter_slug}'")
        raise
    except Exception as e:
         logger.exception(f"Erro inesperado ao buscar manga ou capítulo inicial: {e}")
         raise Http404(f"Erro ao carregar dados do mangá ou capítulo: {e}")

    if request.user.is_authenticated:
        ReadingHistory.objects.update_or_create(
            user=request.user,
            chapter=current_chapter
        )

    user_is_vip = (request.user.is_authenticated and (
        request.user.is_staff or 
        (hasattr(request.user, 'assinatura_vip') and request.user.assinatura_vip and request.user.assinatura_vip.esta_ativa)
    ))
    
    vip_status = current_chapter.get_vip_status()

    if vip_status.get('is_blocked') and not user_is_vip:
        context = {
            'manga': manga,
            'page': current_chapter,
            'chapter': current_chapter,
            'vip_status': vip_status
        }
        return render(request, 'manga/chapter_locked.html', context)

    if not request.user.is_superuser and not request.user.is_staff:
        try:
            MangaChapterPage.objects.filter(pk=current_chapter.pk).update(views=F('views') + 1)
            MangaPage.objects.filter(pk=manga.pk).update(views_count=F('views_count') + 1)
            current_chapter.refresh_from_db(fields=['views'])
        except Exception as e:
            logger.error(f"DEBUG (VIEW): ERRO ao tentar fazer update das views: {e}")

    first_image_instance = current_chapter.chapter_images.order_by('sort_order').first()
    
    chapter_images_urls = []
    if first_image_instance and first_image_instance.encrypted_file.name:
        chapter_image_directory = os.path.dirname(first_image_instance.encrypted_file.path)
        try:
            image_filenames = sorted([f for f in os.listdir(chapter_image_directory) if f.lower().endswith('.avif')])
            media_root_path = settings.MEDIA_ROOT
            media_url = settings.MEDIA_URL
            relative_chapter_path = os.path.relpath(chapter_image_directory, media_root_path)
            for filename in image_filenames:
                image_url = os.path.join(media_url, relative_chapter_path, filename).replace("\\", "/")
                chapter_images_urls.append(image_url)
        except FileNotFoundError:
            logger.warning(f"Diretório de imagens não encontrado para o capítulo: {chapter_image_directory}")
        except Exception as e:
            logger.error(f"Erro ao listar arquivos AVIF para o capítulo {current_chapter.id}: {e}")
    
    all_chapters_qs = MangaChapterPage.objects.live().public().child_of(manga).specific()
    all_chapters_for_nav = sorted(list(all_chapters_qs), key=lambda chap: chap._get_numerical_sort_key(), reverse=True)
    prev_chapter, next_chapter = None, None
    try:
        current_index = all_chapters_for_nav.index(current_chapter)
        if current_index < len(all_chapters_for_nav) - 1:
            prev_chapter = all_chapters_for_nav[current_index + 1]
        if current_index > 0:
            next_chapter = all_chapters_for_nav[current_index - 1]
    except (ValueError, IndexError):
        current_index = -1
        
    is_following = request.user.is_authenticated and Favorite.objects.filter(user=request.user, manga=manga).exists()

    unread_notifications = []
    unread_notification_count = 0
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
        unread_notification_count = unread_notifications.count()

    context = {
        'manga': manga, 
        'page': current_chapter, 
        'chapter': current_chapter, 
        'chapter_images_urls': chapter_images_urls, 
        'prev_chapter': prev_chapter, 
        'next_chapter': next_chapter, 
        'chapter_list_sidebar': all_chapters_for_nav, 
        'is_following': is_following,
        'unread_notifications': unread_notifications,
        'unread_notification_count': unread_notification_count
    }
    return render(request, 'manga/chapter_reader.html', context)

def manga_detail_view(request, manga_slug):
    manga = get_object_or_404(MangaPage.objects.live().public(), slug=manga_slug)
    chapters_qs = MangaChapterPage.objects.live().public().child_of(manga)

    current_sort = request.GET.get('sort', 'desc')
    if current_sort == 'asc':
        chapters_qs = chapters_qs.order_by('first_published_at')
    else:
        chapters_qs = chapters_qs.order_by('-first_published_at')

    search_query = request.GET.get('q_chapter', '')
    if search_query:
        chapters_qs = chapters_qs.filter(title__icontains=search_query)

    chapter_count = chapters_qs.count()

    paginator = Paginator(chapters_qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    is_following = False
    read_chapter_ids = set()
    if request.user.is_authenticated:
        is_following = Favorite.objects.filter(user=request.user, manga=manga).exists()
        read_chapter_ids = set(
            ReadingHistory.objects.filter(
                user=request.user,
                chapter_id__in=[chapter.id for chapter in page_obj]
            ).values_list('chapter_id', flat=True)
        )

    followers_count = Favorite.objects.filter(manga=manga).count()

    context = {
        'page': manga,
        'manga': manga,
        'chapters': page_obj,
        'is_following': is_following,
        'followers_count': followers_count,
        'chapter_count': chapter_count,
        'current_sort': current_sort,
        'search_query': search_query,
        'read_chapter_ids': read_chapter_ids,
    }
    return render(request, 'manga/manga_detail.html', context)

@login_required
@require_POST
def donate_to_manga_view(request, manga_slug):
    try:
        data = json.loads(request.body)
        amount = int(data.get('amount'))

        if amount <= 0:
            return JsonResponse({'status': 'error', 'message': _('A quantidade de moedas deve ser positiva.')}, status=400)

        with transaction.atomic():
            user_profile = request.user.profile.__class__.objects.select_for_update().get(user=request.user)
            
            if user_profile.moedas < amount:
                return JsonResponse({'status': 'error', 'message': _('Você não tem moedas suficientes para esta doação.')}, status=400)

            user_profile.moedas -= amount
            user_profile.save(update_fields=['moedas'])

            manga = get_object_or_404(MangaPage.objects.select_for_update(), slug=manga_slug)
            manga.current_donations += amount
            manga.save(update_fields=['current_donations'])
            
            manga.refresh_from_db()

            return JsonResponse({
                'status': 'success',
                'message': _('Obrigado por doar {} moedas para {}!').format(amount, manga.title),
                'new_user_balance': user_profile.moedas,
                'new_manga_donations': manga.current_donations,
                'donation_goal': manga.donation_goal
            })

    except MangaPage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': _('Obra não encontrada.')}, status=404)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': _('Dados inválidos na requisição.')}, status=400)
    except Exception as e:
        logger.error(f"Erro ao processar doação de moedas para '{manga_slug}': {e}")
        return JsonResponse({'status': 'error', 'message': _('Ocorreu um erro interno. Tente novamente mais tarde.')}, status=500)

def manga_list_all_view(request):
    visible_mangas = MangaPage.objects.visible_for(request.user)
    base_queryset_novels = getattr(NovelPage, 'objects', NovelPage.objects)
    if hasattr(base_queryset_novels, 'visible_for'):
        visible_novels = base_queryset_novels.visible_for(request.user)
    else:
        visible_novels = base_queryset_novels.live().public()
    visible_manga_ids = list(visible_mangas.values_list('pk', flat=True))
    visible_novel_ids = list(visible_novels.values_list('pk', flat=True))
    all_visible_ids = visible_manga_ids + visible_novel_ids
    all_works_qs = Page.objects.filter(pk__in=all_visible_ids).specific()
    q_title = request.GET.get('q_title')
    orderby = request.GET.get('orderby', '-first_published_at')
    status = request.GET.get('status')
    genres = request.GET.getlist('genre')
    if q_title: all_works_qs = all_works_qs.filter(title__icontains=q_title)
    if orderby in ['title', '-title', 'first_published_at', '-first_published_at']: all_works_qs = all_works_qs.order_by(orderby)
    else: all_works_qs = all_works_qs.order_by('-first_published_at')
    paginator = Paginator(all_works_qs, 24)
    page_number = request.GET.get('page')
    try: page_obj = paginator.page(page_number)
    except PageNotAnInteger: page_obj = paginator.page(1)
    except EmptyPage: page_obj = paginator.page(paginator.num_pages)
    context = {'page_title': 'Catálogo de Obras', 'mangas_page_obj': page_obj, 'status_choices': MangaStatus.choices, 'all_genres': Tag.objects.all().order_by('name'), 'selected_genres': genres}
    return render(request, 'manga/comics.html', context)

@login_required 
@require_POST   
def add_comment_view(request, page_id):
    try: page_object = Page.objects.get(pk=page_id).specific
    except Page.DoesNotExist:
        messages.error(request, _("A página onde você tentou comentar não foi encontrada."))
        return redirect(request.META.get('HTTP_REFERER', '/'))
    
    form = MangaCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False); comment.user = request.user; comment.page = page_object; comment.save()
        messages.success(request, _("Seu comentário foi adicionado com sucesso!"))
    else:
        for field, errors in form.errors.items():
            for error in errors: messages.error(request, f"{form.fields[field].label if field != '__all__' else ''}: {error}")
    return redirect(page_object.get_url())

def serve_encrypted_slice(request, chapter_id, slice_id):
    try:
        slice_obj = get_object_or_404(ChapterImage, pk=slice_id, page__pk=chapter_id)
        base_name, _ = os.path.splitext(slice_obj.encrypted_file.name)
        avif_path = f"{base_name}.avif"
        if os.path.exists(avif_path):
             with open(avif_path, 'rb') as f:
                 return HttpResponse(f.read(), content_type='image/avif')

        decrypted_data = slice_obj.decrypt_and_get_data()
        if decrypted_data:
            return HttpResponse(decrypted_data, content_type='image/webp')
        else:
            logger.error(f"Falha na descriptografia para ChapterImage PK: {slice_id}"); raise Http404()
    except Http404:
        logger.warning(f"Slice inexistente: chapter_id={chapter_id}, slice_id={slice_id}"); raise
    except Exception as e:
        logger.exception(f"Erro fatal em serve_encrypted_slice: {e}"); return HttpResponse("Erro interno no servidor.", status=500)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_manga_list_api(request):
    try:
        all_mangas = MangaPage.objects.live().public().order_by('title')
        manga_data = [{'id': manga.pk, 'title': manga.title} for manga in all_mangas]
        return Response({'mangas': manga_data})
    except Exception as e:
        logger.error(f"Erro na API get_manga_list_api: {e}")
        return Response({'error': 'Erro ao buscar a lista de obras.'}, status=500)

@api_view(['POST'])
@permission_classes([IsAdminUser])
@transaction.atomic
def process_chapter_zip_api(request):
    logger.info(f"API: process_chapter_zip_api chamada. Usuário: {request.user}")
    manga_id = request.data.get('manga_page_id')
    chapter_number_str = request.data.get('chapter_number', '').strip()
    zip_file_obj = request.FILES.get('chapter_files')
    chapter_thumbnail_file = request.FILES.get('chapter_thumbnail')
    replace_mode = request.data.get('replace', 'false').lower() == 'true'
    if not all([manga_id, chapter_number_str, zip_file_obj]):
        logger.warning(f"API: Falha - Dados da requisição incompletos.")
        return Response({'status': 'error', 'message': 'ID do Mangá, número do capítulo ou arquivo ZIP não fornecido.'}, status=400)
    try:
        manga_page = get_object_or_404(MangaPage, pk=manga_id)
        existing_chapter = MangaChapterPage.objects.child_of(manga_page).filter(chapter_number=chapter_number_str).first()
        chapter_page = None
        if existing_chapter:
            if replace_mode:
                logger.info(f"API: MODO SUBSTITUIR para cap '{chapter_number_str}' de '{manga_page.title}'.")
                for image in existing_chapter.chapter_images.all():
                    if image.encrypted_file:
                        try:
                            image.encrypted_file.delete(save=False)
                        except Exception as e:
                            logger.error(f"Não foi possível apagar o arquivo físico {image.encrypted_file.name}: {e}")
                existing_chapter.chapter_images.all().delete()
                chapter_page = existing_chapter
                chapter_page.owner = request.user
                chapter_page.last_published_at = timezone.now()
            else:
                logger.warning(f"API: CONFLITO - Cap '{chapter_number_str}' já existe.")
                return Response({'status': 'error', 'message': f'O Capítulo {chapter_number_str} já existe. Use o modo "Substituir".'}, status=409)
        else:
            chapter_page = MangaChapterPage(title=f"{manga_page.title} - Capítulo {chapter_number_str}", chapter_number=chapter_number_str, owner=request.user, is_vip=manga_page.default_chapters_are_vip)
            manga_page.add_child(instance=chapter_page)
            logger.info(f"API: Criando novo cap '{chapter_number_str}'.")

        if chapter_thumbnail_file:
            try:
                if chapter_page.cover:
                    chapter_page.cover.delete(save=False)
                
                new_filename = f"{slugify(chapter_page.title)}.avif"
                chapter_page.cover.save(new_filename, chapter_thumbnail_file, save=False)
                logger.info(f"API: Thumbnail nova salva em {chapter_page.cover.name}")
            except Exception as thumb_e:
                logger.error(f"API: Erro ao processar thumbnail: {thumb_e}", exc_info=True)
        
        chapter_page.save()
        
        images_to_create = []
        with zipfile.ZipFile(zip_file_obj, 'r') as zipf:
            file_list_in_zip = sorted([name for name in zipf.namelist() if not name.startswith('__MACOSX/') and not name.endswith('/') and name.lower().endswith('.avif')])
            
            for index, filename_in_zip in enumerate(file_list_in_zip):
                file_content = zipf.read(filename_in_zip)
                
                django_file = ContentFile(file_content, name=os.path.basename(filename_in_zip))
                
                images_to_create.append(ChapterImage(
                    page=chapter_page, 
                    encrypted_file=django_file, 
                    original_filename=os.path.basename(filename_in_zip), 
                    sort_order=index
                ))
        
        ChapterImage.objects.bulk_create(images_to_create)
        files_processed_count = len(images_to_create)
        
        chapter_page.save_revision(user=request.user).publish(user=request.user)
        logger.info(f"API: Capítulo '{chapter_page.title}' publicado com sucesso.")
        return Response({'status': 'success', 'message': f'Capítulo {chapter_number_str} processado com {files_processed_count} imagens AVIF.', 'chapter_id': chapter_page.pk, 'chapter_url': chapter_page.get_url() if hasattr(chapter_page, 'get_url') else None})
    except Exception as e:
        logger.exception(f"API: Erro INESPERADO em process_chapter_zip_api: {e}")
        return Response({'status': 'error', 'message': f'Erro interno no servidor: {str(e)}'}, status=500)

def load_more_releases(request):
    page_number = int(request.GET.get('page', 2))
    items_per_page = 12
    all_items = []
    if MangaPage:
        latest_chapter_publish_date_subquery = MangaChapterPage.objects.filter(
            path__startswith=OuterRef('path'),
            depth=OuterRef('depth') + 1,
            live=True,
            first_published_at__isnull=False
        ).order_by('-first_published_at').values('first_published_at')[:1]
        latest_mangas = MangaPage.objects.visible_for(request.user).annotate(
            latest_activity_date=Subquery(latest_chapter_publish_date_subquery, output_field=DateTimeField(null=True)),
            item_type=Value('manga', output_field=CharField())
        ).filter(latest_activity_date__isnull=False)
        all_items.extend(list(latest_mangas))
    if NovelPage:
        latest_novel_chapter_date_subquery = NovelChapterPage.objects.filter(
            path__startswith=OuterRef('path'),
            depth=OuterRef('depth') + 1,
            live=True,
            first_published_at__isnull=False
        ).order_by('-first_published_at').values('first_published_at')[:1]
        base_queryset_novels = getattr(NovelPage, 'objects', NovelPage.objects)
        visible_novels_qs = base_queryset_novels.visible_for(request.user) if hasattr(base_queryset_novels, 'visible_for') else base_queryset_novels.live().public()
        latest_novels = visible_novels_qs.annotate(
            latest_activity_date=Subquery(latest_novel_chapter_date_subquery, output_field=DateTimeField(null=True)),
            item_type=Value('novel', output_field=CharField())
        ).filter(latest_activity_date__isnull=False)
        all_items.extend(list(latest_novels))
        
    sorted_items = sorted(all_items, key=operator.attrgetter('latest_activity_date'), reverse=True)
    
    start_index = (page_number - 1) * items_per_page
    end_index = start_index + items_per_page
    
    page_items = sorted_items[start_index:end_index]
    has_next = len(sorted_items) > end_index

    html = render_to_string(
        'includes/manga_card_list.html',
        {'mangas_to_load': page_items}
    )
    
    return JsonResponse({'html': html, 'has_next': has_next})

@login_required
def reading_history_view(request):
    history_entries = list(ReadingHistory.objects.filter(
        user=request.user
    ).order_by('-read_at').select_related('chapter')[:200])

    if not history_entries:
        return render(request, 'manga/reading_history.html', {'history_list': []})

    parent_page_ids = {entry.chapter.get_parent().pk for entry in history_entries}
    parent_mangas = MangaPage.objects.live().public().filter(pk__in=parent_page_ids).specific()
    parents_by_id = {manga.pk: manga for manga in parent_mangas}

    for entry in history_entries:
        parent_id = entry.chapter.get_parent().pk
        entry.chapter.manga = parents_by_id.get(parent_id)

    valid_history_entries = [entry for entry in history_entries if hasattr(entry.chapter, 'manga') and entry.chapter.manga is not None]

    if not valid_history_entries:
        return render(request, 'manga/reading_history.html', {'history_list': []})

    grouped_history = []
    
    current_group = {
        'manga': valid_history_entries[0].chapter.manga,
        'start_chapter': valid_history_entries[0].chapter,
        'end_chapter': valid_history_entries[0].chapter,
        'read_at': valid_history_entries[0].read_at
    }

    for i in range(1, len(valid_history_entries)):
        current_entry = valid_history_entries[i]
        prev_entry = valid_history_entries[i-1]

        is_different_manga = current_entry.chapter.manga.id != current_group['manga'].id
        
        is_not_consecutive = True
        try:
            prev_num = float(prev_entry.chapter.chapter_number)
            current_num = float(current_entry.chapter.chapter_number)
            if prev_num - 1 == current_num:
                is_not_consecutive = False
        except (ValueError, TypeError):
            is_not_consecutive = True

        is_large_time_gap = (prev_entry.read_at - current_entry.read_at) > timedelta(hours=6)

        if is_different_manga or is_not_consecutive or is_large_time_gap:
            grouped_history.append(current_group)
            current_group = {
                'manga': current_entry.chapter.manga,
                'start_chapter': current_entry.chapter,
                'end_chapter': current_entry.chapter,
                'read_at': current_entry.read_at
            }
        else:
            current_group['start_chapter'] = current_entry.chapter
    
    grouped_history.append(current_group)
    
    final_history_list = grouped_history[:50]

    context = {
        'history_list': final_history_list,
    }
    
    return render(request, 'manga/reading_history.html', context)