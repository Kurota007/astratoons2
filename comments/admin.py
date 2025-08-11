from django.contrib import admin
from .models import Comment, Notification

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'page', 'created_at', 'is_approved', 'parent')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('content', 'user__username', 'page__title')
    actions = ['approve_comments']

    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Aprovar comentários selecionados"

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'comment', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'comment__user__username')