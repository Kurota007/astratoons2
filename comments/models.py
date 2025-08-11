from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from wagtail.models import Page

class Comment(models.Model):
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_("Página")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_comments',
        verbose_name=_("Usuário")
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_("Resposta a")
    )
    content = models.TextField(_("Comentário"), blank=True)
    image = models.ImageField(
        _("Imagem Anexada"),
        upload_to='comment_images/%Y/%m/',
        blank=True, 
        null=True
    )
    is_spoiler = models.BooleanField(_("Texto é Spoiler?"), default=False)
    image_is_spoiler = models.BooleanField(_("Imagem é Spoiler?"), default=False)
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    is_approved = models.BooleanField(_("Aprovado"), default=True)
    is_edited = models.BooleanField(_("Editado"), default=False)

    class Meta:
        ordering = ['created_at']
        verbose_name = _("Comentário")
        verbose_name_plural = _("Comentários")

    def __str__(self):
        has_content = "com texto" if self.content else "sem texto"
        has_image = "com imagem" if self.image else "sem imagem"
        return f'Comentário de {self.user.username} em {self.page.title} ({has_content}, {has_image})'

    @property
    def likes(self):
        return self.votes.filter(vote=CommentVote.LIKE).count()

    @property
    def dislikes(self):
        return self.votes.filter(vote=CommentVote.DISLIKE).count()

class CommentVote(models.Model):
    LIKE = 1
    DISLIKE = -1
    VOTE_CHOICES = (
        (LIKE, 'Like'),
        (DISLIKE, 'Dislike'),
    )
    comment = models.ForeignKey(
        Comment, 
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    vote = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')
        verbose_name = _("Voto de Comentário")
        verbose_name_plural = _("Votos de Comentários")

    def __str__(self):
        return f'{self.user.username} votou em comentário {self.comment.id} ({self.get_vote_display()})'

class NotificationManager(models.Manager):
    def unread_for_user(self, user):
        if not user.is_authenticated:
            return self.none()
        return self.filter(user=user, is_read=False)

class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        verbose_name=_("Usuário Notificado")
    )
    comment = models.ForeignKey(
        Comment, 
        on_delete=models.CASCADE,
        verbose_name=_("Comentário de Resposta")
    )
    is_read = models.BooleanField(_("Lido"), default=False)
    created_at = models.DateTimeField(_("Data de Criação"), auto_now_add=True)

    objects = NotificationManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Notificação")
        verbose_name_plural = _("Notificações")

    def __str__(self):
        return f'Notificação para {self.user.username} sobre o comentário de {self.comment.user.username}'