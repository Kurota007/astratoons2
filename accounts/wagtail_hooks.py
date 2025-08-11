# accounts/wagtail_hooks.py

from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from wagtail.admin.panels import Panel
from wagtail import hooks
from wagtail_modeladmin.options import ModelAdmin, ModelAdminGroup, modeladmin_register

from .models import Profile, CosmeticBadge, UserBadge

try:
    from subscriptions.models import AssinaturaUsuario
    SUBSCRIPTIONS_APP_AVAILABLE = True
except ImportError:
    SUBSCRIPTIONS_APP_AVAILABLE = False


# Seu painel customizado existente (INTACTO)
class AssinaturaVipPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        template_name = "wagtailadmin/panels/assinatura_vip_panel.html"
        
        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            user = self.instance 
            assinatura = None
            if SUBSCRIPTIONS_APP_AVAILABLE:
                assinatura = AssinaturaUsuario.objects.filter(usuario=user).first()
            planos_vip_url = reverse('wagtailsnippets_subscriptions_planovip:list')
            context.update({
                'user': user,
                'assinatura': assinatura,
                'subscriptions_available': SUBSCRIPTIONS_APP_AVAILABLE,
                'planos_vip_url': planos_vip_url,
            })
            return context


@hooks.register('register_user_edit_panel')
def register_assinatura_vip_panel():
    return AssinaturaVipPanel(
        heading=_("Status VIP"),
        classname="vip-status-panel",
        order=1000
    )

# Novas telas para gerenciar a Loja de Badges
class CosmeticBadgeAdmin(ModelAdmin):
    model = CosmeticBadge
    menu_label = _("Loja de Badges")  # <-- MARCADO PARA TRADUÇÃO
    menu_icon = "tag"
    list_display = ('name', 'price', 'color', 'is_staff_only')
    list_filter = ('is_staff_only',)
    search_fields = ('name',)

class UserBadgeAdmin(ModelAdmin):
    model = UserBadge
    menu_label = _("Inventário de Badges")  # <-- MARCADO PARA TRADUÇÃO
    menu_icon = "user"
    list_display = ('user', 'badge', 'purchased_at')
    list_filter = ('badge',)
    search_fields = ('user__username', 'badge__name')

class BadgeManagementGroup(ModelAdminGroup):
    menu_label = _("Loja de Badges")  # <-- MARCADO PARA TRADUÇÃO
    menu_icon = "pick"
    menu_order = 210
    items = (CosmeticBadgeAdmin, UserBadgeAdmin)

modeladmin_register(BadgeManagementGroup)