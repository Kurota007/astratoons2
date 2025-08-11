from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

def user_site_avatar_path(instance, filename):
    return f'users/site_avatars/user_{instance.user.id}/{filename}'

class CosmeticBadge(models.Model):
    name = models.CharField(_("Nome do Badge"), max_length=50, unique=True, help_text="Ex: Apoiador Lendário")
    description = models.CharField(_("Descrição"), max_length=150, blank=True, help_text="Uma breve descrição que pode aparecer na loja.")
    icon_class = models.CharField(_("Classe do Ícone (Font Awesome)"), max_length=50, blank=True, help_text="Opcional. Ex: 'fas fa-shield-alt'")
    color = models.CharField(_("Cor de Fundo (Hex)"), max_length=7, default="#4F46E5", help_text="Cor do fundo do badge. Ex: #4F46E5")
    text_color = models.CharField(_("Cor do Texto (Hex)"), max_length=7, default="#FFFFFF", help_text="Cor do texto do badge. Ex: #FFFFFF")
    price = models.PositiveIntegerField(_("Preço em Moedas"), default=1000, help_text="Custo para comprar este badge. 0 para gratuito (mas ainda precisa ser 'comprado').")
    is_staff_only = models.BooleanField(_("Badge de Staff?"), default=False, help_text="Se marcado, este badge é atribuído automaticamente para a equipe e não pode ser comprado.")
    is_vip_badge = models.BooleanField(_("Badge VIP?"), default=False, help_text="Se marcado, este badge é atribuído automaticamente para usuários VIP.")

    class Meta:
        verbose_name = "Badge Cosmético"
        verbose_name_plural = "Loja de Badges"
        ordering = ['price', 'name']

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Usuário"
    )
    display_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nome de Exibição",
        help_text="Como você gostaria de ser chamado no site."
    )
    bio = models.TextField(blank=True, null=True, verbose_name="Biografia")
    location = models.CharField(max_length=100, blank=True, null=True, verbose_name="Localização")
    site_avatar = models.ImageField(
        upload_to=user_site_avatar_path,
        null=True,
        blank=True,
        verbose_name="Avatar do Site",
        help_text="Faça upload de uma imagem para seu avatar neste site."
    )
    moedas = models.IntegerField(_("Saldo de Moedas"), default=0)

    active_badges = models.ManyToManyField(
        CosmeticBadge,
        blank=True,
        related_name='wearers',
        verbose_name="Badges Ativos",
        help_text="Os badges que o usuário escolheu para exibir."
    )

    def get_display_badges(self):
        display_badges = []
        
        is_vip = hasattr(self.user, 'assinatura_vip') and self.user.assinatura_vip.esta_ativa
        
        if self.user.is_staff:
            try:
                staff_badge = CosmeticBadge.objects.get(is_staff_only=True)
                display_badges.append(staff_badge)
            except CosmeticBadge.DoesNotExist:
                pass

        if is_vip or self.user.is_staff:
            try:
                vip_badge = CosmeticBadge.objects.get(is_vip_badge=True)
                if vip_badge not in display_badges:
                    display_badges.append(vip_badge)
            except CosmeticBadge.DoesNotExist:
                pass
        
        chosen_badges = self.active_badges.all()
        for badge in chosen_badges:
            if badge not in display_badges:
                display_badges.append(badge)
        
        return display_badges

    def __str__(self):
        return f"Perfil de {self.user.username if self.user else 'Usuário Desconhecido'}"

    def get_display_avatar_url(self):
        if self.site_avatar and hasattr(self.site_avatar, 'url'):
            return self.site_avatar.url

        try:
            social_account = self.user.socialaccount_set.filter(provider='discord').first()
            if not social_account:
                 social_account = self.user.socialaccount_set.filter(provider='google').first()
            
            if social_account:
                if social_account.provider == 'discord':
                    extra_data = social_account.extra_data
                    discord_user_id = extra_data.get('id')
                    avatar_hash = extra_data.get('avatar')
                    if discord_user_id and avatar_hash:
                        return f"https://cdn.discordapp.com/avatars/{discord_user_id}/{avatar_hash}.png?size=128"
                elif social_account.provider == 'google':
                    return social_account.get_avatar_url()
        except Exception:
            pass

        if hasattr(self.user, 'email') and self.user.email:
            try:
                from django_gravatar.helpers import get_gravatar_url, has_gravatar
                if has_gravatar(self.user.email):
                    return get_gravatar_url(self.user.email, size=128, default='identicon')
            except ImportError:
                pass
        
        from django.templatetags.static import static
        return static('images/default_avatar.png')

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuário"
        ordering = ['user__username']

class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='badge_inventory'
    )
    badge = models.ForeignKey(
        CosmeticBadge,
        on_delete=models.CASCADE,
        related_name='owners'
    )
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')
        verbose_name = "Badge de Usuário"
        verbose_name_plural = "Inventário de Badges"
        ordering = ['-purchased_at']

    def __str__(self):
        return f"{self.user.username} possui o badge '{self.badge.name}'"

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            Profile.objects.create(user=instance)
    except Exception as e:
        logger.error(f"Erro ao salvar ou criar perfil para {instance.username}: {e}")