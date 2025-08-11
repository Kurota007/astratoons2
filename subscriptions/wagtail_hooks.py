# subscriptions/wagtail_hooks.py (ou admin.py)

from django.utils.translation import gettext_lazy as _
from wagtail_modeladmin.options import ModelAdmin, modeladmin_register
from .models import PlanoVIP, AssinaturaUsuario, Transacao, CoinPackage

from accounts.models import Profile

class UserCoinsAdmin(ModelAdmin):
    model = Profile
    menu_label = _("Saldos de Moedas")
    menu_icon = "pilcrow"
    menu_order = 202
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = ('user', 'moedas')
    list_editable = ('moedas',)
    search_fields = ('user__username', 'user__email')

class PlanoVIPAdmin(ModelAdmin):
    model = PlanoVIP
    menu_label = _('Planos VIP')
    menu_icon = 'crown'
    menu_order = 199
    add_to_settings_menu = False
    exclude_from_explorer = False
    # --- CORREÇÃO: 'preco' foi renomeado para 'price' ---
    list_display = ('nome', 'price', 'duracao_dias', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome',)

class AssinaturaUsuarioAdmin(ModelAdmin):
    model = AssinaturaUsuario
    menu_label = _('Assinaturas de Usuários')
    menu_icon = 'user'
    menu_order = 200
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = ('usuario', 'plano', 'data_fim', 'esta_ativa')
    
    list_filter = ('plano',) 
    
    search_fields = ('usuario__username', 'usuario__email')

    def esta_ativa(self, obj):
        return obj.esta_ativa
    esta_ativa.boolean = True
    esta_ativa.short_description = _('Ativa?')

class TransacaoAdmin(ModelAdmin):
    model = Transacao
    menu_label = _('Transações de Pagamento')
    menu_icon = 'list-ul'
    menu_order = 201
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = ('livepix_reference', 'usuario', 'plano', 'status', 'created_at')
    list_filter = ('status', 'plano')
    search_fields = ('livepix_reference', 'usuario__username')

class CoinPackageAdmin(ModelAdmin):
    model = CoinPackage
    menu_label = _("Pacotes de Moedas")
    menu_icon = "cogs"
    menu_order = 205 
    add_to_settings_menu = False
    exclude_from_explorer = False
    # O 'price' aqui já estava correto, então nenhuma mudança foi necessária.
    list_display = ('name', 'amount', 'price', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name',)

modeladmin_register(PlanoVIPAdmin)
modeladmin_register(AssinaturaUsuarioAdmin)
modeladmin_register(TransacaoAdmin)
modeladmin_register(UserCoinsAdmin)
modeladmin_register(CoinPackageAdmin)