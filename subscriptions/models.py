# subscriptions/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid # Importa a biblioteca para gerar IDs únicos

class PlanoVIP(models.Model):
    nome = models.CharField(
        _("Nome do Plano"),
        max_length=100,
        unique=True,
        help_text=_("Ex: VIP Mensal")
    )
    descricao = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descreva os benefícios deste plano.")
    )
    # --- ATUALIZAÇÃO: Unificado para um único campo de preço ---
    price = models.DecimalField(
        _("Preço"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Valor do plano. A moeda (R$ ou US$) será definida nas Configurações Globais do site.")
    )
    duracao_dias = models.PositiveIntegerField(
        _("Duração em Dias"),
        help_text=_("Número de dias que a assinatura ficará ativa. Ex: 30 para mensal, 365 para anual.")
    )
    ativo = models.BooleanField(
        _("Plano Ativo"),
        default=True,
        help_text=_("Desmarque para esconder este plano da página de assinaturas.")
    )
    livepix_plan_id = models.CharField(
        _("LivePix Plan ID"),
        max_length=100, 
        blank=True, 
        null=True, 
        help_text=_("O ID do Plano correspondente criado no painel da LivePix (ex: plan_xxxx...).")
    )
    
    class Meta:
        verbose_name = _("Plano VIP")
        verbose_name_plural = _("Planos VIP")
        ordering = ['price']

    def __str__(self):
        return f"{self.nome} - {self.price}"


class AssinaturaUsuario(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assinatura_vip',
        verbose_name=_("Usuário")
    )
    plano = models.ForeignKey(
        PlanoVIP,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assinantes',
        verbose_name=_("Plano Assinado")
    )
    data_inicio = models.DateTimeField(
        _("Data de Início"),
        default=timezone.now
    )
    data_fim = models.DateTimeField(
        _("Data de Expiração"),
        db_index=True
    )
    
    class Meta:
        verbose_name = _("Assinatura de Usuário")
        verbose_name_plural = _("Assinaturas de Usuários")
        ordering = ['-data_fim']

    def __str__(self):
        return f"Assinatura de {self.usuario.username} expira em {self.data_fim.strftime('%d/%m/%Y')}"

    @property
    def esta_ativa(self):
        return self.data_fim > timezone.now()

    def estender_assinatura(self, plano_adicional):
        ponto_de_partida = max(self.data_fim, timezone.now())
        self.data_fim = ponto_de_partida + timezone.timedelta(days=plano_adicional.duracao_dias)
        self.plano = plano_adicional
        self.save()


class Transacao(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('PAID', 'Pago'),
        ('FAILED', 'Falhou'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transacoes'
    )
    plano = models.ForeignKey(PlanoVIP, on_delete=models.SET_NULL, null=True, blank=True)
    pacote_moedas = models.ForeignKey('CoinPackage', on_delete=models.SET_NULL, null=True, blank=True)

    livepix_reference = models.CharField(
        max_length=255, 
        unique=True, 
        help_text=_("ID de referência retornado pela API da LivePix")
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transação LivePix {self.livepix_reference} - {self.status}"


class CoinPackage(models.Model):
    name = models.CharField(_("Nome do Pacote"), max_length=100, help_text="Ex: Pacote de 100 Moedas")
    description = models.TextField(_("Descrição"), blank=True, help_text="Opcional. Dê mais detalhes sobre o pacote.")
    
    amount = models.PositiveIntegerField(_("Quantidade de Moedas"), help_text="Quantas moedas o usuário receberá.")
    
    # --- ATUALIZAÇÃO: Unificado para um único campo de preço ---
    price = models.DecimalField(_("Preço"), max_digits=10, decimal_places=2, help_text="Valor do pacote. A moeda (R$ ou US$) será definida nas Configurações Globais do site.")
    
    livepix_product_id = models.CharField(
        _("LivePix Product ID (Opcional)"), 
        max_length=100, 
        blank=True, 
        null=True, 
        help_text=_("O ID do produto ou da cobrança correspondente na LivePix.")
    )
    
    is_active = models.BooleanField(_("Ativo na Loja?"), default=True, help_text="Desmarque para esconder este pacote da loja sem deletá-lo.")
    
    order = models.PositiveIntegerField(_("Ordem de Exibição"), default=0, help_text="Pacotes com números menores aparecem primeiro na loja.")

    class Meta:
        verbose_name = _("Pacote de Moedas")
        verbose_name_plural = _("Pacotes de Moedas")
        ordering = ['order', 'price']

    def __str__(self):
        return f"{self.name} ({self.amount} moedas) - {self.price}"

# --- ATUALIZAÇÃO: Modelo para rastrear pedidos do PayPal (ajustado) ---
class PaypalOrder(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuário"))
    subscription_plan = models.ForeignKey(PlanoVIP, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Plano VIP"))
    coin_package = models.ForeignKey(CoinPackage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Pacote de Moedas"))
    invoice_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_("ID da Fatura"))
    # O campo amount_usd foi renomeado para 'amount' para ser genérico
    amount = models.DecimalField(_("Valor"), max_digits=10, decimal_places=2)
    is_completed = models.BooleanField(_("Pagamento Concluído"), default=False)
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    paypal_transaction_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("ID da Transação PayPal"))

    class Meta:
        verbose_name = _("Pedido PayPal")
        verbose_name_plural = _("Pedidos PayPal")
        ordering = ['-created_at']

    def __str__(self):
        produto = self.subscription_plan if self.subscription_plan else self.coin_package
        return f"Pedido PayPal {self.invoice_id} por {self.user.username} - Produto: {produto}"