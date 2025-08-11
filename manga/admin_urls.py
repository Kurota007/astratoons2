# manga/admin_urls.py
from django.urls import path
from . import admin_views

app_name = 'manga_upload_admin'

urlpatterns = [
    path('', admin_views.upload_options_view, name='upload_options'),
    path('zip/', admin_views.combined_upload_zip_view, name='combined_upload_zip'),
    path('folders/', admin_views.folder_upload_view, name='folder_upload'),
    path('api/process-folder/', admin_views.process_chapter_folder_api, name='api_process_chapter_folder'),
]