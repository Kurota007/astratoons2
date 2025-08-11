import json
import logging
import os
import re
import html
import zipfile
import io

import markdown
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from allauth.socialaccount.models import SocialAccount

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .chapter_processing import (
    parse_pdf_text_into_chapters,
    replace_custom_image_tags_in_html,
)
from .forms import PDFUploadForm, SingleChapterForm, ZipUploadForm
from .models import Favorite, NovelChapterPage, NovelPage
from subscriptions.models import AssinaturaUsuario

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfReader = None


@login_required
def user_favorites_view(request):
    all_favorites = Favorite.objects.filter(user=request.user).select_related('novel').order_by('-created_at')
    context = {
        'favorites_list': all_favorites,
    }
    return render(request, 'novels/user_favorites_template.html', context)


@login_required
def api_toggle_favorite_view(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    try:
        data = json.loads(request.body)
        novel_id = data.get('novel_id')
        if not novel_id:
            return JsonResponse({'status': 'error', 'message': 'ID da novel não fornecido.'}, status=400)

        novel_page = get_object_or_404(NovelPage, id=novel_id)
        favorite_instance = Favorite.objects.filter(user=request.user, novel=novel_page).first()

        if favorite_instance:
            favorite_instance.delete()
            is_favorited_now = False
            action_result = 'removed'
        else:
            Favorite.objects.create(user=request.user, novel=novel_page)
            is_favorited_now = True
            action_result = 'added'

        try:
            role_id = novel_page.discord_series_role_id
            if role_id and hasattr(settings, 'DISCORD_BOT_TOKEN') and settings.DISCORD_BOT_TOKEN:
                social_account = request.user.socialaccount_set.get(provider='discord')
                discord_user_id = social_account.uid
                
                url = f"https://discord.com/api/v10/guilds/{settings.DISCORD_GUILD_ID}/members/{discord_user_id}/roles/{role_id}"
                headers = {"Authorization": f"Bot {settings.DISCORD_BOT_TOKEN}"}
                
                if is_favorited_now:
                    response = requests.put(url, headers=headers)
                else:
                    response = requests.delete(url, headers=headers)
                
                if response.status_code not in [200, 201, 204]:
                     logger.warning(f"Discord API Error: {response.status_code} - {response.text}")
        except SocialAccount.DoesNotExist:
            logger.warning(f"User {request.user.username} is trying to favorite but has no Discord account linked.")
        except Exception as e_discord:
            logger.error(f"An unexpected Discord integration error occurred: {e_discord}")

        return JsonResponse({
            'status': 'ok',
            'action': action_result,
            'is_favorited': is_favorited_now
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
    except NovelPage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Novel não encontrada.'}, status=404)
    except Exception as e:
        logger.error(f"Erro inesperado em api_toggle_favorite_view: {type(e).__name__}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno no servidor.'}, status=500)


def chapter_reader_view(request, novel_slug, chapter_slug):
    novel_page = get_object_or_404(NovelPage.objects.live(), slug=novel_slug)
    chapter_page = get_object_or_404(
        NovelChapterPage.objects.live().descendant_of(novel_page),
        slug=chapter_slug
    )
    
    if chapter_page.is_vip:
        user_has_access = False
        if request.user.is_authenticated:
            if request.user.is_staff or request.user.is_superuser:
                user_has_access = True
            else:
                try:
                    if request.user.assinatura_vip.esta_ativa:
                        user_has_access = True
                except AssinaturaUsuario.DoesNotExist:
                    pass

        if not user_has_access:
            messages.warning(request, _("Este é um capítulo exclusivo para assinantes VIP."))
            return redirect('subscriptions:plans_page')

    return chapter_page.serve(request)

WAGTAIL_STYLE_BLOCK = """
<style>
    :root { --w-bg-surface-page: #1e1f21; --w-color-text-primary: #f2f3f4; --w-bg-surface-panel: #2b2c2e; --w-color-text-link: #89b8ff; }
    body { background-color: var(--w-bg-surface-page); color: var(--w-color-text-primary); font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol"; margin: 0; }
    main { padding: 2.5rem; } h1, h3 { margin: 0 0 1rem 0; font-weight: 600; }
    h1 { font-size: 2rem; } h3 { font-size: 1.25rem; }
    em { font-style: italic; }
    .w-card { background-color: var(--w-bg-surface-panel); border-radius: 5px; padding: 1.5rem; }
    ul { list-style: none; padding: 0; margin: 0; } li { margin-bottom: 0.5rem; }
    a { color: var(--w-color-text-link); text-decoration: none; } a:hover { text-decoration: underline; }
    .w-button { display: inline-block; background-color: #333; color: white; padding: 0.75rem 1.5rem; border-radius: 5px; text-decoration: none; margin-top: 1rem; }
</style>
"""

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def novel_chapter_uploader_index_view(request):
    novels = NovelPage.objects.live().order_by('title')
    context = {
        'novels': novels,
        'header_icon': 'folder-upload-alt',
        'page_title': 'Upar Capítulos - Selecione a Obra',
    }
    return render(request, 'novels/admin/novel_chapter_uploader_index.html', context)


@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def novel_chapter_uploader_add_single_view(request, novel_id):
    novel = get_object_or_404(NovelPage, id=novel_id)
    if request.method == 'POST':
        form = SingleChapterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            final_display_title = data['chapter_identifier']
            if data.get('chapter_name_optional'):
                final_display_title += f" - {data['chapter_name_optional']}"
            try:
                sortable_number = float(data['chapter_identifier'].replace(',', '.'))
            except ValueError:
                sortable_number = 0.0
                identifier_lower = data['chapter_identifier'].lower()
                if 'prólogo' in identifier_lower: sortable_number = -1.0
                elif 'epílogo' in identifier_lower: sortable_number = 999999.0
                elif 'introdução' in identifier_lower: sortable_number = -0.5
            
            html_content_from_js = data.get('main_content_html')
            final_html_for_saving = ""

            if html_content_from_js:
                final_html_for_saving = replace_custom_image_tags_in_html(html_content_from_js)
            elif data.get('markdown_content'):
                markdown_text = data['markdown_content']
                html_from_markdown = markdown.markdown(markdown_text, extensions=['extra', 'nl2br', 'fenced_code'])
                final_html_for_saving = replace_custom_image_tags_in_html(html_from_markdown)
            else:
                messages.error(request, "Nenhum conteúdo de capítulo fornecido.")
            
            if final_html_for_saving or final_html_for_saving == "":
                new_chapter = NovelChapterPage(
                    title=f"{novel.title} - {final_display_title}",
                    chapter_display_title=final_display_title,
                    chapter_number_sortable=sortable_number,
                    main_content=final_html_for_saving,
                    is_vip=novel.default_chapters_are_vip
                )
                novel.add_child(instance=new_chapter)
                revision = new_chapter.save_revision(user=request.user)
                revision.publish()
                messages.success(request, f"Capítulo '{new_chapter.chapter_display_title}' adicionado com sucesso a '{novel.title}'.")
                form = SingleChapterForm() 
    else:
        form = SingleChapterForm()
    context = {
        'novel': novel,
        'form': form,
        'header_icon': 'doc-full-inverse',
        'page_title': f"Adicionar Capítulo para: {novel.title}",
        'action_url': reverse('novels:novel_chapter_uploader_add_single', args=[novel.id]),
    }
    return render(request, 'novels/admin/novel_chapter_uploader_add_single.html', context)


@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def novel_chapter_uploader_add_zip_view(request, novel_id):
    novel = get_object_or_404(NovelPage, id=novel_id)
    processed_files_info = [] 

    if request.method == 'POST':
        form = ZipUploadForm(request.POST, request.FILES)
        if form.is_valid():
            zip_file_uploaded = request.FILES['zip_file']
            
            if not zipfile.is_zipfile(zip_file_uploaded):
                messages.error(request, "O arquivo enviado não é um arquivo ZIP válido.")
            else:
                try:
                    with zipfile.ZipFile(zip_file_uploaded, 'r') as zf:
                        file_list = sorted(zf.namelist())
                        processed_files_info.append({'status': 'info', 'message': f"Arquivos encontrados no ZIP: {len(file_list)}"})

                        for filename_in_zip in file_list:
                            if filename_in_zip.startswith('__MACOSX') or filename_in_zip.endswith('/'):
                                continue

                            file_content_bytes = zf.read(filename_in_zip)
                            
                            try:
                                file_text_content = file_content_bytes.decode('utf-8')
                            except UnicodeDecodeError:
                                file_text_content = file_content_bytes.decode('latin-1')
                            
                            chapters_from_file = []
                            if filename_in_zip.lower().endswith(('.txt', '.md')):
                                base_name = os.path.splitext(os.path.basename(filename_in_zip))[0]
                                separator_match = re.match(r"^([^\s_:-]+)[\s_:-]+(.+)$", base_name)
                                
                                if separator_match:
                                    identifier = separator_match.group(1).strip()
                                    raw_name = separator_match.group(2).strip()
                                    cleaned_name = raw_name.replace('-', ' ').replace('_', ' ')
                                    name_opt = cleaned_name.capitalize()
                                else:
                                    identifier = base_name
                                    name_opt = ""

                                html_from_markdown = markdown.markdown(file_text_content, extensions=['extra', 'nl2br', 'fenced_code'])
                                final_html = replace_custom_image_tags_in_html(html_from_markdown)
                                chapters_from_file.append({
                                    'identifier': identifier,
                                    'name_optional': name_opt,
                                    'html_content': final_html,
                                    'sort_num': 0
                                })
                            
                            for chap_data in chapters_from_file:
                                final_chap_display_title = f"Capítulo {chap_data['identifier']}"
                                if chap_data.get('name_optional'):
                                    final_chap_display_title += f" - {chap_data['name_optional']}"
                                
                                try:
                                    sortable_part = chap_data['identifier']
                                    num_match = re.search(r"(\d+[\.,]?\d*)", sortable_part)
                                    if num_match: sort_num = float(num_match.group(1).replace(',', '.'))
                                    else: sort_num = float(sortable_part.replace(',', '.'))
                                except ValueError:
                                    sort_num = 0.0
                                
                                new_db_chapter = NovelChapterPage(
                                    title=f"{novel.title} - {final_chap_display_title}",
                                    chapter_display_title=final_chap_display_title,
                                    chapter_number_sortable=sort_num,
                                    main_content=chap_data['html_content'],
                                    is_vip=novel.default_chapters_are_vip
                                )
                                novel.add_child(instance=new_db_chapter)
                                rev = new_db_chapter.save_revision(user=request.user)
                                rev.publish()
                                processed_files_info.append({'status': 'success', 'message': f"Capítulo '{final_chap_display_title}' criado com sucesso."})
                except Exception as e_zip:
                    messages.error(request, f"Ocorreu um erro ao processar o arquivo ZIP: {str(e_zip)}")
    else:
        form = ZipUploadForm()

    context = {
        'novel': novel,
        'form': form,
        'processed_files_info': processed_files_info,
        'header_icon': 'folder-upload-alt',
        'page_title': f"Upload de Capítulos (ZIP) para: {novel.title}",
        'action_url': reverse('novels:novel_chapter_uploader_add_zip', args=[novel.id]),
    }
    return render(request, 'novels/admin/novel_chapter_uploader_add_zip.html', context)


@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def novel_chapter_uploader_add_pdf_view(request, novel_id):
    novel = get_object_or_404(NovelPage, id=novel_id)

    if request.method != 'POST':
        form = PDFUploadForm()
        context = {
            'novel': novel,
            'form': form,
            'processed_files_info': [],
            'header_icon': 'pdf',
            'page_title': f"Upload de PDF(s) para: {novel.title}",
            'action_url': reverse('novels:novel_chapter_uploader_add_pdf', args=[novel.id]),
        }
        return render(request, 'novels/admin/novel_chapter_uploader_add_pdf.html', context)

    uploaded_files = request.FILES.getlist('pdf_files')
    if not uploaded_files:
        messages.error(request, "Nenhum arquivo enviado. Por favor, selecione um ou mais arquivos PDF.")
        return redirect('novels:novel_chapter_uploader_add_pdf', novel_id=novel.id)

    def stream_response_generator():
        yield '<!DOCTYPE html><html lang="pt-br">'
        yield f'<head><title>Processando...</title><meta name="viewport" content="width=device-width, initial-scale=1">{WAGTAIL_STYLE_BLOCK}</head>'
        yield '<body><main>'
        yield f'<h1>Processando PDF(s) para: <em>{html.escape(novel.title)}</em></h1>'
        yield '<div class="w-card"><h3>Resultados do Processamento:</h3><ul>'
        try:
            sorted_files = sorted(uploaded_files, key=lambda f: f.name)
            yield f'<li>{len(sorted_files)} arquivo(s) recebido(s). Iniciando leitura...</li>'

            if not PYPDF_AVAILABLE:
                yield '<li>Erro: Biblioteca PyPDF não encontrada.</li>'
                raise StopIteration

            full_extracted_text = ""
            for pdf_file in sorted_files:
                yield f'<li>Lendo arquivo: {html.escape(pdf_file.name)}...</li>'
                pdf_stream = io.BytesIO(pdf_file.read())
                reader = PdfReader(pdf_stream)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_extracted_text += page_text + "\n\n"
            
            if not full_extracted_text.strip():
                yield '<li>Aviso: Nenhum texto extraído dos PDFs.</li>'
                raise StopIteration
            
            chapters = parse_pdf_text_into_chapters(full_extracted_text)
            
            if not chapters:
                yield '<li>Aviso: Nenhum capítulo válido encontrado no texto combinado.</li>'
                raise StopIteration

            yield f'<li>Texto combinado dividido em {len(chapters)} capítulos. Iniciando salvamento...</li>'

            with transaction.atomic():
                for chap_data in chapters:
                    final_chap_display_title = f"Capítulo {chap_data['identifier']}"
                    if chap_data.get('name_optional'):
                        final_chap_display_title += f" - {chap_data['name_optional']}"
                    
                    sort_num = chap_data.get('sort_num', 0.0)
                    
                    new_db_chapter = NovelChapterPage(
                        title=f"{novel.title} - {final_chap_display_title}",
                        chapter_display_title=final_chap_display_title,
                        chapter_number_sortable=sort_num,
                        main_content=chap_data['html_content'],
                        is_vip=novel.default_chapters_are_vip
                    )
                    novel.add_child(instance=new_db_chapter)
                    rev = new_db_chapter.save_revision(user=request.user)
                    rev.publish()
                    
                    edit_url = reverse('wagtailadmin_pages:edit', args=[new_db_chapter.id])
                    yield f'<li><a href="{edit_url}" target="_blank">{html.escape(final_chap_display_title)}</a> - criado com sucesso.</li>'

            yield '<li style="font-weight: bold; margin-top: 1rem;">Processo concluído com sucesso!</li>'

        except Exception as e:
            logger.error(f"Erro inesperado no processamento de PDF: {e}", exc_info=True)
            yield f'<li style="color: red;">ERRO INESPERADO: {html.escape(str(e))}</li>'
            yield f'<li style="color: red;">O processo foi interrompido.</li>'
        
        yield '</ul></div>'
        yield f'<a href="{reverse("novels:novel_chapter_uploader_index")}" class="w-button">Voltar para a lista de obras</a>'
        yield '</main></body></html>'

    return StreamingHttpResponse(stream_response_generator())


@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def test_markdown_file_processing_view(request, novel_id):
    novel = get_object_or_404(NovelPage, id=novel_id)
    file_path = r'E:\Users\sergio\Desktop\reaper\conteudo_extraido_do_pdf.txt'
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            extracted_text = f.read()
    except Exception as e:
        return HttpResponse(f"<h1>Erro na Leitura do Arquivo</h1><p>{html.escape(str(e))}</p>", status=500)

    parsed_chapters = parse_pdf_text_into_chapters(extracted_text)
    response_html = f"<h1>Teste de Divisão para '{html.escape(novel.title)}'</h1>"
    response_html += f"<h2>Texto Lido (primeiros 2000 caracteres):</h2><pre>{html.escape(extracted_text[:2000])}...</pre>"
    response_html += f"<hr><h2>Capítulos Detectados ({len(parsed_chapters)}):</h2>"
    
    for i, chapter in enumerate(parsed_chapters):
        response_html += f"<h3>Capítulo {i+1}</h3><p><strong>Identificador:</strong> '{html.escape(chapter['identifier'])}'</p>"
        if chapter['name_optional']:
            response_html += f"<p><strong>Nome Opcional:</strong> '{html.escape(chapter['name_optional'])}'</p>"
        response_html += f"<h4>Conteúdo Renderizado:</h4><div style='border: 1px solid #ccc; padding: 10px;'>{chapter['html_content']}</div><hr>"
        
    return HttpResponse(response_html)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_get_novel_list(request):
    try:
        novels = NovelPage.objects.live().order_by('title')
        data = [{'id': novel.id, 'title': novel.title} for novel in novels]
        return Response({'novels': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in api_get_novel_list: {e}")
        return Response(
            {'error': 'Internal server error while fetching novel list.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAdminUser])
@transaction.atomic
def api_upload_chapter(request):
    novel_id = request.data.get('novel_page_id')
    chapter_number = request.data.get('chapter_number')
    chapter_title = request.data.get('chapter_title')
    html_content = request.data.get('content')

    if not all([novel_id, chapter_number, chapter_title, html_content]):
        return Response(
            {'status': 'error', 'message': 'Incomplete data provided.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        parent_novel = NovelPage.objects.get(id=novel_id)
    except NovelPage.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Novel with ID {novel_id} not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        wagtail_page_title = f"{parent_novel.title} - {chapter_title}"
        sortable_number = float(str(chapter_number).replace(',', '.'))

        new_chapter = NovelChapterPage(
            title=wagtail_page_title,
            chapter_display_title=chapter_title,
            chapter_number_sortable=sortable_number,
            main_content=html_content,
            owner=request.user,
            is_vip=parent_novel.default_chapters_are_vip
        )
        
        parent_novel.add_child(instance=new_chapter)
        revision = new_chapter.save_revision(user=request.user)
        revision.publish()

        return Response({
            'status': 'success',
            'message': f"Chapter '{chapter_title}' created.",
            'chapter_url': new_chapter.get_url(request=request)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error while saving chapter via API: {e}", exc_info=True)
        return Response(
            {'status': 'error', 'message': 'Internal error while saving chapter.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )