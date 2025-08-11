from django.utils.translation import gettext_lazy as _
from wagtail_modeladmin.options import ModelAdmin, ModelAdminGroup, modeladmin_register
from .models import Comment, Notification

class CommentAdmin(ModelAdmin):
    model = Comment
    menu_label = _('Comentários')
    menu_icon = 'edit'
    list_display = ('user', 'page', 'content_preview', 'created_at', 'is_approved')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('content', 'user__username', 'page__title')

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    
    content_preview.short_description = _('Comentário (início)')

class NotificationAdmin(ModelAdmin):
    model = Notification
    menu_label = _('Notificações')
    menu_icon = 'notification'
    list_display = ('user', 'comment_author', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'comment__user__username')

    def comment_author(self, obj):
        return obj.comment.user.username
    comment_author.short_description = _('Autor da Resposta')

class CommentsGroup(ModelAdminGroup):
    menu_label = _('Gerenciar Comentários')
    menu_icon = 'group'
    menu_order = 290
    items = (CommentAdmin, NotificationAdmin)

modeladmin_register(CommentsGroup)