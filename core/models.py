# core/models.py

import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from pathlib import Path
from django.conf import settings

from modelcluster.models import ClusterableModel
from modelcluster.fields import ParentalKey

from wagtail.models import Orderable, Page
from wagtail.admin.panels import (
    FieldPanel,
    MultiFieldPanel,
    InlinePanel,
    TabbedInterface,
    ObjectList,
    HelpPanel,
    PageChooserPanel,
    FieldRowPanel,
)
from wagtail.contrib.settings.models import BaseSiteSetting, BaseGenericSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.images import get_image_model

Image = get_image_model()

# ================================================================
# == NOVOS MODELOS PARA O SISTEMA DE REAÇÕES
# ================================================================

class ReactionType(Orderable):
    setting = ParentalKey(
        'core.GlobalSettings', 
        on_delete=models.CASCADE, 
        related_name='reaction_types'
    )
    name = models.CharField(_("Nome"), max_length=50, help_text=_("Ex: Gostei, Amei"))
    type_id = models.SlugField(_("ID do Tipo"), max_length=50, unique=True, help_text=_("Identificador único, ex: 'like', 'love'"))
    icon = models.FileField(_("Ícone"), upload_to='reactions/', help_text=_("Ícone da reação (.svg, .png)"))

    panels = [
        FieldPanel('name'),
        FieldPanel('type_id'),
        FieldPanel('icon'),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Tipo de Reação")
        verbose_name_plural = _("Tipos de Reação")

    def __str__(self):
        return self.name

class UserReaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="reactions")
    reaction_type = models.ForeignKey(ReactionType, on_delete=models.CASCADE, related_name="user_reactions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'page')
        verbose_name = _("Reação de Usuário")
        verbose_name_plural = _("Reações de Usuários")

    def __str__(self):
        return f"{self.user.username} reagiu com '{self.reaction_type.name}' em '{self.page.title}'"

# ================================================================
# == FIM DOS NOVOS MODELOS
# ================================================================

class SliderItem(Orderable):
    setting = ParentalKey(
        'core.GlobalSettings',
        on_delete=models.CASCADE,
        related_name='slider_items'
    )
    image = models.ForeignKey(
        Image, null=True, blank=False, on_delete=models.CASCADE,
        related_name='+', verbose_name=_("Imagem do Slide")
    )
    link_page = models.ForeignKey(
        'wagtailcore.Page', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("Link Interno (Página)"),
        help_text=_("Se preenchido, ignora o Link Externo.")
    )
    link_url = models.URLField(
        blank=True, verbose_name=_("Link Externo (URL)"),
        help_text=_("Use apenas se não houver Link Interno.")
    )
    caption = models.CharField(max_length=255, blank=True, verbose_name=_("Legenda (Opcional)"))

    panels = [
        FieldPanel('image'),
        FieldPanel('caption'),
        PageChooserPanel('link_page'),
        FieldPanel('link_url'),
    ]

    @property
    def link(self):
        if self.link_page:
            return self.link_page.get_url()
        elif self.link_url:
            return self.link_url
        return None

    class Meta(Orderable.Meta):
        verbose_name = _("Item do Slider")
        verbose_name_plural = _("Itens do Slider")


class PremiumBenefit(Orderable):
    setting = ParentalKey(
        'core.GlobalSettings',
        on_delete=models.CASCADE,
        related_name='premium_benefits'
    )
    text = models.CharField(max_length=255, verbose_name=_("Texto do Benefício"))

    panels = [
        FieldPanel('text'),
    ]

    def __str__(self):
        return self.text

    class Meta(Orderable.Meta):
        verbose_name = _("Benefício Premium")
        verbose_name_plural = _("Benefícios Premium")


@register_setting(icon='cog')
class GlobalSettings(BaseSiteSetting, ClusterableModel):
    COMMENT_PROVIDERS = [
        ('none', _("Nenhum Sistema de Comentários")),
        ('disqus', _("Disqus")),
        ('custom', _("Sistema Próprio (Custom)")),
    ]
    
    # --- ATUALIZAÇÃO: Opções de Moeda ---
    CURRENCY_CHOICES = [
        ('BRL', _("Real Brasileiro (R$) - Ativa LivePix")),
        ('USD', _("Dólar Americano (US$) - Ativa PayPal")),
    ]

    logo = models.ForeignKey(Image, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name=_("Logo do Site"))
    favicon = models.ForeignKey(Image, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name=_("Favicon"))
    footer_scan_name = models.CharField(max_length=100, blank=True, verbose_name=_("Nome no Rodapé"))
    footer_credits = models.CharField(max_length=200, blank=True, default="Desenvolvido por Stalker", verbose_name=_("Créditos (Rodapé)"))
    discord_link = models.URLField(max_length=255, blank=True, null=True, verbose_name=_("Link do Discord"))
    donation_link = models.URLField(max_length=255, blank=True, null=True, verbose_name=_("Link de Doação"))
    donation_message = RichTextField(blank=True, null=True, features=['bold', 'italic', 'link'], verbose_name=_("Mensagem de Doação (Home)"))
    dmca_text = RichTextField(blank=True, null=True, features=['bold', 'italic', 'link'], verbose_name=_("Texto DMCA"))
    privacy_policy_text = RichTextField(blank=True, null=True, features=['bold', 'italic', 'link'], verbose_name=_("Texto Política de Privacidade"))
    terms_of_use_text = RichTextField(blank=True, null=True, features=['bold', 'italic', 'link'], verbose_name=_("Texto Termos de Uso"))
    activate_slider = models.BooleanField(default=False, verbose_name=_("Ativar Slider na Home?"))
    color_navbar = models.CharField(max_length=7, default="#171717", blank=True, verbose_name=_("Cor Fundo Navbar"))
    color_background = models.CharField(max_length=7, default="#000000", blank=True, verbose_name=_("Cor Fundo Principal"))
    color_text = models.CharField(max_length=7, default="#e0e0e0", blank=True, verbose_name=_("Cor Texto Principal"))
    color_accent = models.CharField(max_length=7, default="#00B982", blank=True, verbose_name=_("Cor de Destaque"))
    color_card_background = models.CharField(max_length=7, default="#18181b", blank=True, verbose_name=_("Cor Fundo Card"))
    color_border = models.CharField(max_length=7, default="#27272a", blank=True, verbose_name=_("Cor Borda"))
    color_text_light = models.CharField(max_length=7, default="#a0a0a0", blank=True, verbose_name=_("Cor Texto Claro"))
    color_input_background = models.CharField(max_length=7, default="#27272a", blank=True, verbose_name=_("Cor Fundo Input"))
    color_input_border = models.CharField(max_length=7, default="#3f3f46", blank=True, verbose_name=_("Cor Borda Input"))
    color_button_primary_text = models.CharField(max_length=7, default="#ffffff", blank=True, verbose_name=_("Cor Texto Botão Primário"))
    color_button_secondary_bg = models.CharField(max_length=7, default="#333333", blank=True, verbose_name=_("Cor Fundo Botão Secundário"))
    color_button_secondary_text = models.CharField(max_length=7, default="#dddddd", blank=True, verbose_name=_("Cor Texto Botão Secundário"))
    color_button_secondary_border = models.CharField(max_length=7, default="#555555", blank=True, verbose_name=_("Cor Borda Botão Secundário"))
    color_danger = models.CharField(max_length=7, default="#ef4444", blank=True, verbose_name=_("Cor Perigo"))
    color_section_background = models.CharField(max_length=7, default="#101013", blank=True, verbose_name=_("Cor Fundo Seção"))
    new_chapter_days_threshold = models.PositiveIntegerField(default=2, verbose_name=_("Limite de Dias para Badge Automático"))
    new_chapter_badge_text = models.CharField(max_length=20, default="NOVO!", blank=True, verbose_name=_("Texto Padrão do Badge 'Novo Capítulo'"))
    new_chapter_badge_image = models.ForeignKey(Image, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name=_("Imagem/GIF Padrão do Badge 'Novo Capítulo' (Opcional)"))
    livepix_widget_url = models.URLField(blank=True, null=True, verbose_name=_("URL do Widget LivePix (Home)"))
    comment_provider = models.CharField(max_length=50, choices=COMMENT_PROVIDERS, default='disqus', verbose_name=_("Provedor de Comentários"))
    disqus_shortname = models.CharField(max_length=100, blank=True, verbose_name=_("Disqus Shortname"))
    
    # --- ATUALIZAÇÃO: Campo de escolha de moeda ---
    default_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='BRL',
        verbose_name=_("Moeda Padrão do Site"),
        help_text=_("Selecione a moeda principal para os preços e o método de pagamento a ser exibido.")
    )

    livepix_client_id = models.CharField(max_length=255, blank=True, verbose_name=_("LivePix Client ID"), help_text=_("Client ID obtido do painel de desenvolvedor do LivePix."))
    livepix_client_secret = models.CharField(max_length=255, blank=True, verbose_name=_("LivePix Client Secret"), help_text=_("Client Secret obtido do painel de desenvolvedor. Mantenha em segredo."))
    
    paypal_receiver_email = models.EmailField(blank=True, verbose_name=_("PayPal Receiver Email"), help_text=_("O email da sua conta de vendedor do PayPal."))
    paypal_client_id = models.CharField(max_length=255, blank=True, verbose_name=_("PayPal Client ID (Live)"), help_text=_("Client ID da sua aplicação PayPal para pagamentos reais."))
    paypal_client_secret = models.CharField(max_length=255, blank=True, verbose_name=_("PayPal Client Secret (Live)"), help_text=_("Client Secret para pagamentos reais. Mantenha em segredo."))
    paypal_sandbox_client_id = models.CharField(max_length=255, blank=True, verbose_name=_("PayPal Client ID (Sandbox)"), help_text=_("Client ID para o ambiente de testes (Sandbox)."))
    paypal_sandbox_client_secret = models.CharField(max_length=255, blank=True, verbose_name=_("PayPal Client Secret (Sandbox)"), help_text=_("Client Secret para o ambiente de testes. Mantenha em segredo."))
    
    recent_vip_chapter_limit = models.PositiveIntegerField(default=5, verbose_name=_("Limite de Capítulos Recentes VIP"), help_text=_("Para obras não-VIP, define quantos dos últimos capítulos lançados serão exclusivos para assinantes."))
    discord_bot_token = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Token do Bot do Discord"), help_text=_("O token do seu bot para gerenciar cargos e enviar anúncios. Mantenha em segredo."))
    discord_guild_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("ID do Servidor (Guild)"), help_text=_("O ID do seu servidor do Discord."))
    discord_vip_role_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("ID do Cargo VIP"), help_text=_("O ID do cargo que será dado aos assinantes VIP."))
    ad_script_monetag = models.TextField(blank=True, null=True, verbose_name=_("Monetag (Meta Tag de Verificação)"), help_text=_("Cole a meta tag <meta name='monetag'...> aqui."))
    ad_script_pertawee = models.TextField(blank=True, null=True, verbose_name=_("Push Notifications"), help_text=_("ID da Zona: 9469896"))
    ad_script_push_antiblock = models.TextField(blank=True, null=True, verbose_name=_("Push Notifications (Anti-AdBlock)"), help_text=_("ID da Zona: 9469897"))
    ad_script_al5sm = models.TextField(blank=True, null=True, verbose_name=_("OnClick (Popunder)"), help_text=_("ID da Zona: 9469898"))
    ad_script_loajawun = models.TextField(blank=True, null=True, verbose_name=_("In-Page Push"), help_text=_("ID da Zona: 9469961"))
    ad_script_groleegni = models.TextField(blank=True, null=True, verbose_name=_("Native Banner (Interstitial)"), help_text=_("ID da Zona: 9469963"))
    ad_script_stoampaliy = models.TextField(blank=True, null=True, verbose_name=_("Vignette Banner"), help_text=_("ID da Zona: 9469964"))
    ad_script_multizone = models.TextField(blank=True, null=True, verbose_name=_("Monetag (Multizone)"), help_text=_("Cole o script do anúncio Multizone aqui."))
    
    use_canvas_reader = models.BooleanField(
        default=True,
        verbose_name=_("Usar Canvas para Leitor de Capítulos"),
        help_text=_("Se marcado, as páginas dos capítulos serão exibidas em <canvas> para dificultar o download. Se desmarcado, usará a tag <img> padrão.")
    )

    activate_premium_banner = models.BooleanField(default=False, verbose_name=_("Ativar Banner Premium na Home?"))
    premium_banner_badge = models.CharField(max_length=100, blank=True, default="Premium", verbose_name=_("Badge do Banner"))
    premium_banner_title = models.CharField(max_length=200, blank=True, default="Desbloqueie funcionalidades exclusivas", verbose_name=_("Título do Banner"))
    premium_banner_price = models.CharField(max_length=50, blank=True, default="R$ 5,00/mês", verbose_name=_("Texto de Preço"))
    premium_banner_button_text = models.CharField(max_length=50, blank=True, default="Assinar Agora", verbose_name=_("Texto do Botão"))
    premium_banner_benefits_title = models.CharField(max_length=100, blank=True, default="Vantagens Premium", verbose_name=_("Título da Lista de Benefícios"))

    premium_banner_gif = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_("GIF Animado do Banner"),
        help_text=_("Opcional. Um GIF para ser exibido ao lado do banner.")
    )

    cloudflare_zone_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Cloudflare Zone ID"),
        help_text=_("O ID da Zona encontrado no painel do Cloudflare. Necessário para limpar o cache.")
    )
    cloudflare_api_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Cloudflare API Token"),
        help_text=_("Crie um token com permissão de 'Purge Cache'. Ele será usado para limpar o cache automaticamente.")
    )


    identidade_panels = [
        MultiFieldPanel([ FieldPanel('logo'), FieldPanel('favicon'), FieldPanel('footer_scan_name'), FieldPanel('footer_credits'), ], heading=_("Identidade Visual e Rodapé")),
        MultiFieldPanel([ FieldPanel('discord_link'), FieldPanel('donation_link'), FieldPanel('donation_message'), ], heading=_("Links Sociais e Apoio")),
        MultiFieldPanel([ FieldPanel('dmca_text'), FieldPanel('privacy_policy_text'), FieldPanel('terms_of_use_text'), ], heading=_("Textos Legais"), classname="collapsible collapsed"),
    ]
    slider_panels = [
        FieldPanel('activate_slider'),
        InlinePanel('slider_items', label=_("Item do Slider"), min_num=0, max_num=8)
    ]
    premium_banner_panels = [
        MultiFieldPanel([
            FieldPanel('activate_premium_banner'),
            FieldPanel('premium_banner_badge'),
            FieldPanel('premium_banner_title'),
            FieldPanel('premium_banner_price'),
        ], heading=_("Conteúdo Principal do Banner")),
        MultiFieldPanel([
            FieldPanel('premium_banner_button_text'),
        ], heading=_("Botão de Ação (CTA)")),
        MultiFieldPanel([
            FieldPanel('premium_banner_benefits_title'),
            InlinePanel('premium_benefits', label=_("Benefício"), min_num=1, max_num=6),
        ], heading=_("Lista de Benefícios")),
        MultiFieldPanel([
            FieldPanel('premium_banner_gif'),
        ], heading=_("Visual (GIF Animado)")),
    ]
    aparencia_panels = [
        HelpPanel(content=_("Defina as cores principais. Use códigos hexadecimais (ex: #00B982). Deixar em branco usará o padrão definido no CSS.")),
        FieldRowPanel([ FieldPanel('color_navbar', classname="col6"), FieldPanel('color_background', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_text', classname="col6"), FieldPanel('color_accent', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_card_background', classname="col6"), FieldPanel('color_border', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_text_light', classname="col6"), FieldPanel('color_input_background', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_input_border', classname="col6"), FieldPanel('color_button_primary_text', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_button_secondary_bg', classname="col6"), FieldPanel('color_button_secondary_text', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_button_secondary_border', classname="col6"), FieldPanel('color_danger', classname="col6"), ]),
        FieldRowPanel([ FieldPanel('color_section_background', classname="col6") ]),
    ]
    
    conteudo_panels = [
        MultiFieldPanel([
            FieldPanel('new_chapter_days_threshold'),
            FieldPanel('new_chapter_badge_text'),
            FieldPanel('new_chapter_badge_image'),
        ], heading=_("Configurações do Badge 'Novo Capítulo'")),
        MultiFieldPanel([
            FieldPanel('recent_vip_chapter_limit'),
        ], heading=_("Configurações de Acesso VIP")),
        MultiFieldPanel([
            FieldPanel('use_canvas_reader'),
        ], heading=_("Configurações do Leitor de Capítulos")),
    ]

    comentarios_panels = [
        HelpPanel(content=_("Configure o sistema de comentários do site.")),
        FieldPanel('comment_provider'),
        FieldPanel('disqus_shortname'),
    ]

    reacoes_panels = [
        HelpPanel(content=_("Adicione e gerencie os tipos de reações disponíveis para os usuários.")),
        InlinePanel('reaction_types', label=_("Tipo de Reação"))
    ]

    # --- ATUALIZAÇÃO: Adicionado painel de escolha de moeda ---
    monetizacao_panels = [
        MultiFieldPanel([
            FieldPanel('default_currency'),
        ], heading=_("Configurações de Moeda")),
        MultiFieldPanel([
            FieldPanel('ad_script_monetag'),
            FieldPanel('ad_script_pertawee'),
            FieldPanel('ad_script_push_antiblock'),
            FieldPanel('ad_script_al5sm'),
            FieldPanel('ad_script_loajawun'),
            FieldPanel('ad_script_groleegni'),
            FieldPanel('ad_script_stoampaliy'),
            FieldPanel('ad_script_multizone'),
        ], heading="Códigos de Anúncio (Monetag)", classname="collapsible collapsed"),
        MultiFieldPanel([
            FieldPanel('livepix_widget_url'),
            FieldPanel('livepix_client_id'),
            FieldPanel('livepix_client_secret'),
        ], heading=_("Configurações do LivePix"), classname="collapsible collapsed"),
        MultiFieldPanel([
            FieldPanel('paypal_receiver_email'),
            FieldPanel('paypal_client_id'),
            FieldPanel('paypal_client_secret'),
            FieldPanel('paypal_sandbox_client_id'),
            FieldPanel('paypal_sandbox_client_secret'),
        ], heading=_("Configurações do PayPal"), classname="collapsible collapsed"),
        MultiFieldPanel([
            FieldPanel('discord_bot_token'),
            FieldPanel('discord_guild_id'),
            FieldPanel('discord_vip_role_id'),
        ], heading=_("Integração do Bot do Discord"), classname="collapsible collapsed"),
        MultiFieldPanel([
            FieldPanel('cloudflare_zone_id'),
            FieldPanel('cloudflare_api_token'),
        ], heading=_("Integração do Cloudflare"), classname="collapsible collapsed"),
    ]

    edit_handler = TabbedInterface([
        ObjectList(identidade_panels, heading=_('Identidade e Links')),
        ObjectList(slider_panels, heading=_('Slider Home')),
        ObjectList(premium_banner_panels, heading=_('Banner Premium Home')),
        ObjectList(aparencia_panels, heading=_('Aparência')),
        ObjectList(conteudo_panels, heading=_('Conteúdo & VIP')),
        ObjectList(comentarios_panels, heading=_('Comentários')),
        ObjectList(reacoes_panels, heading=_('Reações')),
        ObjectList(monetizacao_panels, heading=_('Monetização e Integrações')),
    ])

    class Meta:
        verbose_name = _("Configurações Globais do Site")


@register_setting(icon='share-alt')
class SocialProviderSettings(BaseGenericSetting):
    google_client_id = models.CharField(max_length=255, blank=True, verbose_name=_("Google Client ID"))
    google_client_secret = models.CharField(max_length=255, blank=True, verbose_name=_("Google Client Secret"))
    discord_client_id = models.CharField(max_length=255, blank=True, verbose_name=_("Discord Client ID"))
    discord_client_secret = models.CharField(max_length=255, blank=True, verbose_name=_("Discord Client Secret"))

    panels = [
        MultiFieldPanel([FieldPanel("google_client_id"), FieldPanel("google_client_secret")], heading="Google OAuth Settings"),
        MultiFieldPanel([FieldPanel("discord_client_id"), FieldPanel("discord_client_secret")], heading="Discord OAuth Settings"),
    ]

    class Meta:
        verbose_name = "Credenciais de Login Social (OAuth)"