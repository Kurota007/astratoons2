# manga/admin_views.py

import logging
import os
import io
import json
from PIL import Image as PillowImage
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count

from .models import MangaPage, MangaChapterPage, ChapterImage
from .forms import CombinedUploadForm
from .utils import process_manga_zip
from wagtail.models import Locale
from django.conf import settings
from wagtail.images.models import Image as WagtailImage
from pathlib import Path

logger = logging.getLogger(__name__)

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def upload_options_view(request):
    page_title = _("Upar Capítulos - Selecione a Obra")
    header_icon = 'doc-full-inverse'
    all_manga_pages = MangaPage.objects.live().public().order_by('title')

    for page in all_manga_pages:
        try:
            page.safe_chapter_count = page.get_children().count()
        except Exception:
            page.safe_chapter_count = 0

    context_data = {
        'page_title': page_title,
        'header_title': page_title,
        'header_icon': header_icon,
        'all_manga_pages_for_options': all_manga_pages,
    }
    return render(request, 'manga/admin/upload_options.html', context_data)

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def combined_upload_zip_view(request):
    page_title = _("Upar Capítulo(s) por ZIP")
    header_icon = 'doc-full-inverse'

    initial_manga = None
    manga_id_from_url = request.GET.get('manga_id')
    if manga_id_from_url:
        try:
            initial_manga = MangaPage.objects.get(pk=manga_id_from_url)
        except (MangaPage.DoesNotExist, ValueError):
            messages.warning(request, _("A obra selecionada para upload não foi encontrada."))

    if request.method == 'POST':
        form_data = request.POST.copy()
        if initial_manga and 'manga_selection' not in request.POST:
             form_data['manga_selection'] = initial_manga.pk

        form = CombinedUploadForm(form_data, request.FILES)

        if form.is_valid():
            selected_manga = form.cleaned_data['manga_selection']
            zip_file_obj = form.cleaned_data['zip_file']
            owner_user = request.user

            try:
                success, processing_messages = process_manga_zip(
                    manga_page=selected_manga,
                    zip_file_obj=zip_file_obj,
                    owner_user=owner_user
                )
                for level, msg in processing_messages:
                    messages.add_message(request, level, msg)

                if success and not any(level == messages.ERROR for level, msg in processing_messages):
                    if not any(level == messages.SUCCESS for level, msg in processing_messages):
                         messages.success(request, _("Processamento concluído. Verifique os detalhes abaixo."))
                    return redirect(reverse('wagtailadmin_explore', args=[selected_manga.id]))

            except Exception as e:
                logger.exception(f"Erro fatal em combined_upload_zip_view para manga {selected_manga.pk if 'selected_manga' in locals() else 'N/A'}. Erro: {e}")
                messages.error(request, _("Erro fatal inesperado durante o processamento: %(error)s") % {'error': e})
    else:
        form = CombinedUploadForm(initial={'manga_selection': initial_manga} if initial_manga else None)

    context_data = {
        'form': form,
        'page_title': page_title,
        'header_title': page_title,
        'header_icon': header_icon,
        'selected_manga_from_url': initial_manga
    }
    return render(request, 'manga/admin/combined_upload_form.html', context_data)

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def folder_upload_view(request):
    page_title = _("Upar Capítulos por Pastas")
    header_icon = 'folder-open-inverse'

    initial_manga = None
    manga_id_from_url = request.GET.get('manga_id')
    if manga_id_from_url:
        try:
            initial_manga = MangaPage.objects.get(pk=manga_id_from_url)
        except (MangaPage.DoesNotExist, ValueError):
            messages.warning(request, _("A obra selecionada para upload não foi encontrada."))

    all_mangas_for_select = MangaPage.objects.live().order_by('title')

    context_data = {
        'all_manga_pages': all_mangas_for_select,
        'selected_manga_from_url': initial_manga,
        'page_title': page_title,
        'header_title': page_title,
        'header_icon': header_icon,
    }
    # CORREÇÃO DO ERRO 1: Usando o nome do seu template original
    return render(request, 'manga/admin/folder_upload_form.html', context_data)


@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
@require_POST
@transaction.atomic
def process_chapter_folder_api(request):
    try:
        manga_id = request.POST.get('manga_id')
        chapter_number = request.POST.get('chapter_number')
        files = request.FILES.getlist('files[]')
        thumbnail_file = request.FILES.get('thumbnail') # Pode ser a thumb automática ou manual

        if not all([manga_id, chapter_number, files]):
            return JsonResponse({'status': 'error', 'message': 'Dados incompletos recebidos.'}, status=400)

        manga_page = MangaPage.objects.get(pk=manga_id)

        existing_chapter = MangaChapterPage.objects.child_of(manga_page).filter(chapter_number=chapter_number).first()
        if existing_chapter:
            chapter_page = existing_chapter
            # Só apaga a thumb se uma NOVA for enviada.
            if thumbnail_file and chapter_page.thumbnail:
                chapter_page.thumbnail.delete(save=False)

            for image_instance in chapter_page.chapter_images.all():
                if hasattr(image_instance, 'encrypted_file') and image_instance.encrypted_file:
                    try:
                        os.remove(image_instance.encrypted_file.path)
                    except (FileNotFoundError, AttributeError):
                        pass
            chapter_page.chapter_images.all().delete()
        else:
            chapter_page = MangaChapterPage(
                title=f"{manga_page.title} - Capítulo {chapter_number}",
                chapter_number=chapter_number,
                owner=request.user
            )
            manga_page.add_child(instance=chapter_page)

        save_params = {'format': 'AVIF', 'quality': 55, 'subsampling': '4:2:0', 'speed': 9}
        
        # A lógica para a thumb agora está aqui.
        if thumbnail_file:
            try:
                thumb_img = PillowImage.open(thumbnail_file).convert("RGB")
                buffer = io.BytesIO()
                thumb_img.save(buffer, **save_params) 

                original_thumb_name = Path(thumbnail_file.name)
                new_thumb_filename = original_thumb_name.with_suffix('.avif').name
                
                chapter_page.thumbnail.save(
                    new_thumb_filename,
                    ContentFile(buffer.getvalue()),
                    save=False # Salva no final
                )
            except Exception as e:
                logger.error(f"Erro ao converter a thumbnail para AVIF: {e}")
                chapter_page.thumbnail = thumbnail_file
        
        # Salva o capítulo aqui para ter um PK antes de criar as imagens
        chapter_page.last_published_at = timezone.now()
        chapter_page.save_revision().publish()

        images_to_create = []
        slice_height = getattr(settings, 'ALTURA_FATIA', 1600)
        
        final_image_index = 0
        for uploaded_file in sorted(files, key=lambda f: f.name):
            # ... (Sua lógica original de processar e fatiar imagens continua aqui, sem alterações)
            try:
                img = PillowImage.open(uploaded_file)
                width, height = img.size
                
                if height > slice_height:
                    for y in range(0, height, slice_height):
                        box = (0, y, width, min(y + slice_height, height))
                        slice_img = img.crop(box).convert("RGB")
                        
                        buffer = io.BytesIO()
                        slice_img.save(buffer, **save_params)
                        
                        avif_filename = f"{final_image_index:03d}.avif"
                        
                        images_to_create.append(ChapterImage(
                            page=chapter_page,
                            encrypted_file=ContentFile(buffer.getvalue(), name=avif_filename),
                            original_filename=f"{uploaded_file.name} (slice {final_image_index})",
                            sort_order=final_image_index
                        ))
                        final_image_index += 1
                else:
                    buffer = io.BytesIO()
                    img.convert("RGB").save(buffer, **save_params)
                    
                    original_stem = Path(uploaded_file.name).stem
                    avif_filename = f"{final_image_index:03d}_{original_stem}.avif"

                    images_to_create.append(ChapterImage(
                        page=chapter_page,
                        encrypted_file=ContentFile(buffer.getvalue(), name=avif_filename),
                        original_filename=uploaded_file.name,
                        sort_order=final_image_index
                    ))
                    final_image_index += 1

            except Exception as e:
                logger.error(f"Erro ao processar a imagem {uploaded_file.name}: {e}")
                continue

        ChapterImage.objects.bulk_create(images_to_create)

        return JsonResponse({
            'status': 'success',
            'message': f'Capítulo {chapter_number} processado com {len(images_to_create)} imagens finais.',
            'chapter_url': chapter_page.get_url()
        })

    except MangaPage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Obra não encontrada.'}, status=404)
    except Exception as e:
        logger.exception("Erro inesperado no processamento do capítulo via API.")
        return JsonResponse({'status': 'error', 'message': f'Erro no servidor: {e}'}, status=500)