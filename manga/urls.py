# manga/urls.py

from django.urls import path
from . import views
from . import admin_views # Mantendo a importação do seu admin_views

app_name = 'manga'

urlpatterns = [
    # --- SUAS ROTAS PÚBLICAS (NÃO MEXIDAS) ---
    path('api/toggle-favorite/', views.toggle_favorite_view, name='api_toggle_favorite'),
    path('historico/', views.reading_history_view, name='reading_history'),
    path('comics/', views.manga_list_all_view, name='manga_list_all'),
    path('ajax/load-more-releases/', views.load_more_releases, name='load_more_releases'),
    path('todos/', views.manga_list_all_view, name='manga_list_all'),
    path('<str:manga_slug>/doar/', views.donate_to_manga_view, name='donate_to_manga'),
    path('<str:manga_slug>/capitulo/<str:chapter_slug>/', views.chapter_reader_view, name='chapter_reader'),
    path('<str:manga_slug>/capitulo/<str:chapter_number>/download/', views.download_chapter_zip_view, name='download_chapter_zip'),
    path('imagem-segura/<int:chapter_id>/<int:slice_id>/',  views.serve_encrypted_slice, name='serve_encrypted_slice'),
    path('<str:manga_slug>/', views.manga_detail_view, name='manga_detail'),

    # --- ROTAS DO PAINEL DE UPLOAD (APONTANDO PARA ADMIN_VIEWS) ---
    
    # Rota que MOSTRA a página de upload que você já tinha
    path('admin/manga-uploader/folders/', admin_views.folder_upload_view, name='manga_folder_uploader'),

    # Rota para a API que PROCESSA os arquivos - A CAUSA DO ERRO
    path('admin/manga-uploader/api/process-folder/', admin_views.process_chapter_folder_api, name='api_process_chapter_folder'),

    # Sua rota antiga de upload por zip
    path('admin/manga-uploader/zip/', admin_views.combined_upload_zip_view, name='upload_zip'),
]