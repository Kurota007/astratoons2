# comments/urls.py
from django.urls import path
from . import views

app_name = 'comments'

urlpatterns = [
    path('post/', views.post_comment, name='post_comment'),
    path('delete/<int:comment_id>/', views.delete_comment, name='delete_comment'),
    path('vote/', views.vote_comment, name='vote_comment'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
     path('notifications/mark-all-as-read/', views.mark_all_as_read, name='mark_all_as_read'),
]