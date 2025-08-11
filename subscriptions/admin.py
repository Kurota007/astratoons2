# subscriptions/admin.py

from django.contrib import admin
from .models import PlanoVIP, AssinaturaUsuario, Transacao, CoinPackage

@admin.register(PlanoVIP)
class PlanoVIPAdmin(admin.ModelAdmin):
    # --- CORREÇÃO: 'preco' foi renomeado para 'price' ---
    list_display = ('nome', 'price', 'duracao_dias', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome',)

@admin.register(AssinaturaUsuario)
class AssinaturaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plano', 'data_inicio', 'data_fim', 'esta_ativa')
    list_filter = ('plano', 'data_fim')
    search_fields = ('usuario__username',)
    readonly_fields = ('data_inicio', 'data_fim')

@admin.register(Transacao)
class TransacaoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plano', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('usuario__username', 'livepix_reference')
    readonly_fields = ('created_at', 'updated_at')

# ===================================================================
#           REGISTRO DO PACOTE DE MOEDAS ADICIONADO AQUI
# ===================================================================

@admin.register(CoinPackage)
class CoinPackageAdmin(admin.ModelAdmin):
    """
    Configuração do painel de admin para os Pacotes de Moedas.
    """
    # O 'price' aqui já estava correto, então nenhuma mudança foi necessária.
    list_display = ('name', 'amount', 'price', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    
    # --- CORREÇÃO: 'preco' foi renomeado para 'price' ---
    list_editable = ('price', 'is_active', 'order',)
    
    # --- CORREÇÃO: 'preco' foi renomeado para 'price' ---
    ordering = ['order', 'price']