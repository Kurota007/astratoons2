# novels/urls.py

from django.urls import path
from . import views

app_name = 'novels'

urlpatterns = [
    path('meus-favoritos/', views.user_favorites_view, name='user_favorites'),
    path('api/toggle-favorite/', views.api_toggle_favorite_view, name='api_toggle_favorite'),
    path('upload/', views.novel_chapter_uploader_index_view, name='novel_chapter_uploader_index'),
    path('upload/single/<int:novel_id>/', views.novel_chapter_uploader_add_single_view, name='novel_chapter_uploader_add_single'),
    path('upload/zip/<int:novel_id>/', views.novel_chapter_uploader_add_zip_view, name='novel_chapter_uploader_add_zip'),
    path('upload/pdf/<int:novel_id>/', views.novel_chapter_uploader_add_pdf_view, name='novel_chapter_uploader_add_pdf'),
    path('test-markdown/<int:novel_id>/', views.test_markdown_file_processing_view, name='test_markdown_processing'),
    path('api/get-novel-list/', views.api_get_novel_list, name='api_get_novel_list'),
    path('api/upload-chapter/', views.api_upload_chapter, name='api_upload_chapter'),
    path('<slug:novel_slug>/<slug:chapter_slug>/', views.chapter_reader_view, name='chapter_reader'),
]