import logging
import os
import re
from pathlib import Path
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase
from wagtail.admin.panels import (
    FieldPanel,
    InlinePanel,
    MultiFieldPanel,
    FieldRowPanel,
    HelpPanel,
)
from wagtail.api import APIField
from wagtail.fields import RichTextField
from wagtail.images.models import Image as WagtailImage
from wagtail.models import Page, PageManager, Orderable
from wagtail.documents.models import Document
from wagtail.search import index
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from cryptography.fernet import Fernet, InvalidToken

try:
    from core.models import GlobalSettings
except ImportError:
    GlobalSettings = None

logger = logging.getLogger(__name__)
try:
    from .validator import validate_rating_range
except ImportError:
    def validate_rating_range(value): pass

def chapter_thumb_upload_path(instance, filename):
    manga_page = instance.get_parent().specific
    manga_slug = manga_page.slug if manga_page and manga_page.slug else 'obra-desconhecida'
    chapter_slug = instance.slug or slugify(instance.chapter_number) or 'cap-desconhecido'
    extension = Path(filename).suffix
    new_filename = f"thumb{extension}"
    return f'chapter_thumbnails/{manga_slug}/{chapter_slug}/{new_filename}'

class MangaType(models.TextChoices):
    MANGA = 'MA', _('Manga (Japonês)')
    MANHWA = 'MH', _('Manhwa (Coreano)')
    MANHUA = 'MU', _('Manhua (Chinês)')
    WEBTOON = 'WT', _('Webtoon')
    OTHER = 'OT', _('Outro')

class MangaStatus(models.TextChoices):
    ONGOING = 'OG', _('Em Andamento')
    COMPLETED = 'CP', _('Completo')
    HIATUS = 'HT', _('Hiato')
    CANCELLED = 'CL', _('Cancelado')

class ReleaseDay(models.TextChoices):
    MONDAY = 'MON', _('Segunda-feira')
    TUESDAY = 'TUE', _('Terça-feira')
    WEDNESDAY = 'WED', _('Quarta-feira')
    THURSDAY = 'THU', _('Quinta-feira')
    FRIDAY = 'FRI', _('Sexta-feira')
    SATURDAY = 'SAT', _('Sábado')
    SUNDAY = 'SUN', _('Domingo')
    UNDEFINED = 'UND', _('Indefinido / Sem dia fixo')
    IRREGULAR = 'IRR', _('Irregular')

class MangaPageGenre(TaggedItemBase):
    content_object = ParentalKey('manga.MangaPage', related_name='genre_items', on_delete=models.CASCADE)
    class Meta:
        verbose_name = _("Gênero da Obra")
        verbose_name_plural = _("Gêneros da Obra")

class WorkRelation(Orderable):
    RELATION_CHOICES = [
        ('shared_universe', 'Universo Compartilhado'),
        ('prequel', 'Prequel'),
        ('sequel', 'Sequel'),
        ('spin_off', 'Spin-off'),
        ('main_story', 'História Principal'),
        ('side_story', 'História Paralela'),
        ('pre_serialization', 'Pré-serialização'),
        ('alternative_version', 'Versão Alternativa'),
    ]
    source_work = ParentalKey('manga.MangaPage', on_delete=models.CASCADE, related_name='source_relations', verbose_name="Obra de Origem")
    target_work = models.ForeignKey('manga.MangaPage', on_delete=models.CASCADE, related_name='target_relations', verbose_name="Obra Relacionada")
    relation_type = models.CharField(max_length=50, choices=RELATION_CHOICES, verbose_name="Tipo de Relação")
    panels = [FieldPanel('target_work'), FieldPanel('relation_type')]
    class Meta(Orderable.Meta):
        verbose_name = "Relação de Obra"
        verbose_name_plural = "Relações de Obras"

class MangaChapterUpload(Orderable):
    page = ParentalKey('manga.MangaPage', on_delete=models.CASCADE, related_name='chapter_uploads')
    zip_file = models.FileField(upload_to='chapter_uploads/%Y/%m/', verbose_name=_("Arquivo ZIP"), validators=[FileExtensionValidator(allowed_extensions=['zip'])], help_text=_("Apenas arquivos .zip são permitidos."))
    upload_date = models.DateTimeField(_("Data de Upload"), auto_now_add=True)
    processed = models.BooleanField(_("Processado?"), default=False, db_index=True)
    processed_chapters = models.PositiveIntegerField(_("Capítulos no ZIP"), default=0)
    notes = models.TextField(_("Status/Notas Processamento"), blank=True)
    panels = [FieldPanel('zip_file'), FieldPanel('notes', read_only=True)]
    def __str__(self):
        page_title = self.page.title if self.page else "Página Desconhecida"
        zip_name = os.path.basename(self.zip_file.name) if self.zip_file else "Sem Arquivo"
        status = "Processado" if self.processed else "Pendente"
        return f"Upload p/ '{page_title}' ({zip_name}) - {self.upload_date.strftime('%Y-%m-%d')} [{status}]"
    class Meta(Orderable.Meta):
        verbose_name = _("Upload de Capítulos (Registro)")
        verbose_name_plural = _("Uploads de Capítulos (Registros)")
        ordering = ['-upload_date']

class MangaPageManager(PageManager):
    def visible_for(self, user):
        is_vip_user = user.is_authenticated and (user.is_staff or (hasattr(user, 'assinatura_vip') and user.assinatura_vip.esta_ativa))
        if is_vip_user:
            return self.live().public()
        return self.live().public().filter(chapters_are_vip=False)

class MangaPage(Page):
    manga_type = models.CharField(_("Tipo"), max_length=2, choices=MangaType.choices, default=MangaType.MANHWA)
    status = models.CharField(_("Status"), max_length=2, choices=MangaStatus.choices, default=MangaStatus.ONGOING)
    author = models.CharField(_("Autor(es)"), max_length=255, blank=True)
    artist = models.CharField(_("Artista(s)"), max_length=255, blank=True)
    scanlator = models.CharField(_("Scanlator"), max_length=255, blank=True)
    cover = models.ForeignKey('wagtailimages.Image', verbose_name=_("Capa"), null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    genre = ClusterTaggableManager(_("Gêneros"), through=MangaPageGenre, blank=True)
    rating = models.DecimalField(_("Nota Média (0.0 a 10.0)"), max_digits=3, decimal_places=1, validators=[validate_rating_range], null=True, blank=True)
    description = RichTextField(_("Sinopse"), features=['bold', 'italic', 'link'], blank=True)
    release_day = models.CharField(_("Dia da Semana (Lançamento Aprox.)"), max_length=3, choices=ReleaseDay.choices, blank=True, null=True, help_text=_("Selecione o dia principal que novos capítulos costumam sair."))
    release_year = models.PositiveIntegerField(_("Ano de Lançamento"), blank=True, null=True)
    alternative_titles = models.CharField(_("Títulos Alternativos"), max_length=500, blank=True, null=True)
    publisher = models.CharField(_("Editora/Plataforma"), max_length=255, blank=True, null=True)
    original_link_kr = models.URLField(_("Link Original (Coreano)"), max_length=500, blank=True, null=True)
    original_link_jp = models.URLField(_("Link Original (Japonês)"), max_length=500, blank=True, null=True)
    original_link_cn = models.URLField(_("Link Original (Chinês)"), max_length=500, blank=True, null=True)
    original_link_en = models.URLField(_("Link Oficial (Inglês)"), max_length=500, blank=True, null=True)
    news_updates = RichTextField(_("Notícias e Avisos"), blank=True, null=True, help_text=_("Use este espaço para avisos sobre hiatos, mudanças, informações extras, etc."), features=['h3', 'h4', 'bold', 'italic', 'link', 'ul', 'ol', 'document-link', 'image'])
    discord_series_role_id = models.CharField(_("ID do Cargo no Discord (Notificações)"), max_length=30, blank=True, null=True, help_text=_("Opcional. ID do cargo do Discord a ser mencionado quando novos capítulos desta obra forem lançados."))
    chapters_are_vip = models.BooleanField(_("Obra Inteira é VIP?"), default=False, help_text=_("Se marcado, TODOS os capítulos desta obra exigirão uma assinatura VIP e a obra será escondida de não-assinantes."))
    default_chapters_are_vip = models.BooleanField(_("Ativar VIP para Caps. Recentes?"), default=False, help_text=_("Se marcado, os capítulos mais recentes (definido abaixo) serão VIP."))
    recent_vip_chapters_count = models.PositiveIntegerField(_("Quantidade de Capítulos Recentes VIP"), default=0, help_text=_("Defina quantos dos capítulos mais recentes serão exclusivos para VIPs (ex: 3). Só funciona se a opção acima estiver marcada."))
    vip_tier_size = models.PositiveIntegerField(_("Tamanho do Degrau VIP (caps)"), default=3, help_text=_("Quantos capítulos formam um 'degrau' de tempo de espera. Ex: 3."))
    vip_base_release_days = models.PositiveIntegerField(_("Tempo Máx. de Espera (dias)"), default=7, help_text=_("Tempo de espera, em dias, para os capítulos do degrau mais recente."))
    vip_days_decrease_per_tier = models.PositiveIntegerField(_("Redução de Tempo por Degrau (dias)"), default=2, help_text=_("Quantos dias de espera são removidos a cada degrau mais antigo. Ex: 2."))
    is_up_to_date = models.BooleanField(_("Obra em Dia?"), default=False, help_text=_("Marque se os capítulos postados estão em dia com os lançamentos originais. Isso desativará a caixa de doação."))
    views_count = models.PositiveIntegerField(default=0, editable=False, verbose_name="Contador de Visualizações")
    donation_system_active = models.BooleanField(_("Ativar Sistema de Doação?"), default=False, help_text=_("Marque para habilitar a funcionalidade de meta de doação para esta obra."))
    donation_goal = models.PositiveIntegerField(_("Meta de Moedas para Próximo Cap."), default=0, help_text=_("Defina a meta de moedas para o lançamento do próximo capítulo. 0 para desativar."))
    current_donations = models.PositiveIntegerField(_("Moedas Atuais na Meta"), default=0, help_text=_("Quantidade de moedas doadas até agora para o próximo capítulo."))
    reset_donation_goal_on_save = models.BooleanField(_("Zerar Moedas Atuais ao Salvar?"), default=False, help_text=_("Marque esta caixa e salve para zerar o contador de 'Moedas Atuais na Meta'."))
    donation_notifications_sent = models.PositiveIntegerField(default=0, editable=False, verbose_name="Notificações de Meta Enviadas")
    
    objects = MangaPageManager()

    search_fields = Page.search_fields + [
        index.SearchField('author', partial_match=True, boost=1.2),
        index.SearchField('artist', partial_match=True),
        index.SearchField('description'),
        index.FilterField('manga_type'),
        index.FilterField('status'),
        index.FilterField('rating'),
        index.SearchField('alternative_titles'),
        index.SearchField('publisher'),
        index.RelatedFields('genre', [index.SearchField('name', partial_match=True, boost=1.1), index.FilterField('slug')])
    ]
    content_panels = Page.content_panels + [
        FieldPanel('cover'),
        MultiFieldPanel([
            FieldRowPanel([FieldPanel('manga_type', classname="col6"), FieldPanel('status', classname="col6")]),
            FieldRowPanel([FieldPanel('author', classname="col6"), FieldPanel('artist', classname="col6")]),
            FieldRowPanel([FieldPanel('genre', classname="col6"), FieldPanel('rating', classname="col6")]),
            FieldRowPanel([FieldPanel('release_year', classname="col6"), FieldPanel('release_day', classname="col6")]),
            FieldPanel('is_up_to_date'),
            FieldPanel('alternative_titles'),
            FieldRowPanel([FieldPanel('publisher', classname="col6"), FieldPanel('scanlator', classname="col6")]),
            FieldPanel('discord_series_role_id'),
        ], heading=_("Detalhes da Obra")),
        MultiFieldPanel([
            FieldPanel('chapters_are_vip'),
            FieldPanel('default_chapters_are_vip'),
            FieldPanel('recent_vip_chapters_count'),
            HelpPanel(content=_("As configurações abaixo definem um sistema de desbloqueio progressivo para capítulos VIP.")),
            FieldRowPanel([
                FieldPanel('vip_tier_size', classname="col4"), 
                FieldPanel('vip_base_release_days', classname="col4"), 
                FieldPanel('vip_days_decrease_per_tier', classname="col4")
            ]),
        ], heading=_("Configurações VIP"), classname="collapsible collapsed"),
        MultiFieldPanel([
            HelpPanel(content=_("A caixa de doação só aparecerá se o sistema estiver ativo, a meta for > 0 e a obra NÃO estiver marcada como 'Em Dia'.")),
            FieldPanel('donation_system_active'),
            FieldPanel('donation_goal'),
            FieldPanel('current_donations'),
            FieldPanel('reset_donation_goal_on_save'),
        ], heading=_("Meta de Doação de Capítulo"), classname="collapsible collapsed"),
        MultiFieldPanel([
            FieldPanel('original_link_kr'),
            FieldPanel('original_link_jp'),
            FieldPanel('original_link_cn'),
            FieldPanel('original_link_en'),
        ], heading=_("Links Oficiais/Originais"), classname="collapsible collapsed"),
        FieldPanel('description', heading=_("Sinopse")),
        FieldPanel('news_updates', heading=_("Notícias e Avisos")),
        InlinePanel('source_relations', label="Relações de Obras", help_text="Adicione outras obras que se relacionam com esta.")
    ]

    parent_page_types = ['home.HomePage']
    subpage_types = ['manga.MangaChapterPage']

    api_fields = [
        APIField('manga_type'), APIField('status'), APIField('author'), APIField('artist'),
        APIField('scanlator'), APIField('cover'), APIField('genre'), APIField('rating'), APIField('description'),
        APIField('release_day'), APIField('get_release_day_display'), APIField('release_year'),
        APIField('alternative_titles'), APIField('publisher'), APIField('original_link_kr'),
        APIField('original_link_jp'), APIField('original_link_cn'), APIField('original_link_en'),
        APIField('news_updates'), APIField('discord_series_role_id'), APIField('chapters_are_vip'),
        APIField('default_chapters_are_vip'), APIField('recent_vip_chapters_count'),
        APIField('vip_tier_size'), APIField('vip_base_release_days'), APIField('vip_days_decrease_per_tier'),
        APIField('is_up_to_date'), APIField('views_count'), APIField('donation_system_active'),
        APIField('donation_goal'), APIField('current_donations'), APIField('donation_notifications_sent'),
        APIField('donation_box_visible'),
    ]

    class Meta:
        verbose_name = _("Página de Mangá")
        verbose_name_plural = _("Páginas de Mangá")
        ordering = ['title']

    @property
    def donation_box_visible(self):
        if (self.donation_system_active and 
            self.donation_goal > 0 and 
            not self.is_up_to_date):
            return True
        return False

    @property
    def display_status(self):
        if self.status == MangaStatus.COMPLETED:
            return {'text': 'Completo', 'color': '#22c55e', 'class': 'completed'}
        if self.status == MangaStatus.HIATUS:
            return {'text': 'Hiato', 'color': '#f59e0b', 'class': 'hiatus'}
        if self.status == MangaStatus.CANCELLED:
            return {'text': 'Cancelado', 'color': '#ef4444', 'class': 'cancelled'}
        if self.status == MangaStatus.ONGOING and self.is_up_to_date:
            return {'text': 'Em Dia', 'color': '#1e6a3a', 'class': 'up-to-date'}
        return None

    @property
    def has_vip_chapters(self):
        return self.get_children().live().specific().filter(is_vip=True).exists()
    
    def save(self, *args, **kwargs):
        if self.reset_donation_goal_on_save:
            self.current_donations = 0
            self.reset_donation_goal_on_save = False
        super().save(*args, **kwargs)

    def get_chapters(self):
        all_chapters_qs = MangaChapterPage.objects.child_of(self).live().public().specific()
        all_chapters_list = list(all_chapters_qs)
        chapters_sorted_list = sorted(
            all_chapters_list,
            key=lambda chap: (
                chap._get_numerical_sort_key() if hasattr(chap, '_get_numerical_sort_key') else (float('inf'), float('inf')),
                -(chap.release_date_or_published or timezone.datetime.min.replace(tzinfo=timezone.utc)).timestamp() if hasattr(chap, 'release_date_or_published') and chap.release_date_or_published else float('-inf'),
                chap.title.lower()
            )
        )
        chapters_sorted_list.reverse()
        return chapters_sorted_list

    def get_recent_chapters(self, count=5):
        all_sorted_chapters = self.get_chapters()
        return all_sorted_chapters[:count]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        all_chapters_list = self.get_chapters()
        search_query_val = request.GET.get('q_chapter', '').strip()
        context['search_query'] = search_query_val
        if search_query_val:
            filtered_list = []
            for chapter_obj in all_chapters_list:
                match_title = False
                if hasattr(chapter_obj, 'title') and chapter_obj.title:
                    match_title = search_query_val.lower() in chapter_obj.title.lower()
                match_number = False
                if hasattr(chapter_obj, 'chapter_number') and chapter_obj.chapter_number:
                    match_number = search_query_val.lower() in str(chapter_obj.chapter_number).lower()
                if match_title or match_number:
                    filtered_list.append(chapter_obj)
            all_chapters_list = filtered_list
        sort_param = request.GET.get('sort', 'desc')
        context['current_sort'] = sort_param
        chapters_to_paginate = all_chapters_list
        if sort_param == 'asc':
            chapters_to_paginate.reverse()
        paginator = Paginator(chapters_to_paginate, 25)
        page_number = request.GET.get('page')
        try:
            chapters_paginated = paginator.page(page_number)
        except PageNotAnInteger:
            chapters_paginated = paginator.page(1)
        except EmptyPage:
            chapters_paginated = paginator.page(paginator.num_pages)
        context['chapters'] = chapters_paginated
        is_following_this_manga = False
        current_followers_count = 0
        if 'Favorite' in globals() and hasattr(self, 'favorited_by') and self.favorited_by is not None:
             current_followers_count = self.favorited_by.count()
        if request.user.is_authenticated and 'Favorite' in globals():
            if Favorite.objects.filter(user=request.user, manga=self).exists():
                is_following_this_manga = True
        
        first_chapter_in_current_sort = None
        if chapters_to_paginate:
            first_chapter_in_current_sort = chapters_to_paginate[0]
        
        query_params_desc = request.GET.copy()
        query_params_desc['sort'] = 'desc'; query_params_desc.pop('page', None)
        if search_query_val: query_params_desc['q_chapter'] = search_query_val
        else: query_params_desc.pop('q_chapter', None)
        context['sort_url_desc'] = '?' + query_params_desc.urlencode() if query_params_desc else '?sort=desc'
        
        query_params_asc = request.GET.copy()
        query_params_asc['sort'] = 'asc'; query_params_asc.pop('page', None)
        if search_query_val: query_params_asc['q_chapter'] = search_query_val
        else: query_params_asc.pop('q_chapter', None)
        context['sort_url_asc'] = '?' + query_params_asc.urlencode() if query_params_asc else '?sort=asc'
        
        context.update({
            'chapter_count': len(all_chapters_list) if not search_query_val else len(filtered_list),
            'last_chapter': self.get_chapters()[0] if self.get_chapters() else None,
            'is_following': is_following_this_manga,
            'followers_count': current_followers_count,
            'related_works': MangaPage.objects.live().public().exclude(pk=self.pk).order_by('?')[:5]
        })
        return context

def chapter_image_upload_path(instance, filename):
    manga_page = instance.page.get_parent().specific
    chapter_page = instance.page.specific
    manga_slug = manga_page.slug if manga_page and manga_page.slug else 'obra-desconhecida'
    chapter_number_raw = str(chapter_page.chapter_number) if chapter_page and hasattr(chapter_page, 'chapter_number') else 'cap-desconhecido'
    safe_chapter_folder_name = re.sub(r'[^\w.-]', '_', chapter_number_raw).strip('_')
    if not safe_chapter_folder_name:
        safe_chapter_folder_name = 'cap_extra'
    return f'encrypted_manga_slices/{manga_slug}/{safe_chapter_folder_name}/{filename}'

class ChapterImage(Orderable):
    page = ParentalKey('manga.MangaChapterPage', on_delete=models.CASCADE, related_name='chapter_images')
    encrypted_file = models.FileField(upload_to=chapter_image_upload_path, max_length=255, null=True, blank=False, verbose_name=_("Arquivo de Fatia Criptografada (.enc)"), help_text=_("Armazena a fatia da imagem no formato .enc criptografado."))
    original_filename = models.CharField(_("Nome Original do Arquivo"), max_length=255, blank=True)
    caption = models.CharField(_("Legenda (Opcional)"), max_length=255, blank=True)
    panels = [FieldPanel('encrypted_file'), FieldPanel('original_filename', read_only=True), FieldPanel('caption')]
    def decrypt_and_get_data(self) -> bytes | None:
        if not hasattr(settings, 'CHAVE_MESTRA_IMAGENS') or not settings.CHAVE_MESTRA_IMAGENS:
            return None
        if not self.encrypted_file:
            return None
        try:
            fernet = Fernet(settings.CHAVE_MESTRA_IMAGENS)
            if hasattr(self.encrypted_file, 'seek') and callable(self.encrypted_file.seek):
                 self.encrypted_file.seek(0)
            if hasattr(self.encrypted_file, 'is_open') and self.encrypted_file.is_open:
                encrypted_data = self.encrypted_file.read()
            else:
                with self.encrypted_file.open('rb') as f:
                    encrypted_data = f.read()
            return fernet.decrypt(encrypted_data)
        except (InvalidToken, FileNotFoundError, Exception):
            return None
    def __str__(self):
        return self.original_filename or f"Fatia Criptografada {self.sort_order if hasattr(self, 'sort_order') else 'N/A'} de {self.page.title if self.page else 'Página Desconhecida'}"
    class Meta(Orderable.Meta):
        verbose_name = _("Arquivo de Imagem Criptografada")
        verbose_name_plural = _("Arquivos de Imagem Criptografada")
        ordering = ['sort_order']

class MangaChapterPage(Page):
    template = "manga/chapter_reader.html"
    chapter_number = models.CharField(_("Número/ID do Capítulo"), max_length=20, db_index=True)
    is_vip = models.BooleanField(_("Capítulo VIP?"), default=False, help_text=_("Marque se este capítulo for exclusivo para assinantes VIP."))
    thumbnail = models.ImageField(_("Thumbnail do Capítulo"), upload_to=chapter_thumb_upload_path, null=True, blank=True, help_text=_("Thumbnail específica para este capítulo. Salva fora da biblioteca do Wagtail."))
    background_music = models.ForeignKey('wagtaildocs.Document', null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name=_("Trilha Sonora de Fundo (BGM)"), help_text=_("Opcional. Escolha um arquivo de áudio (MP3, OGG) para tocar durante a leitura deste capítulo."))
    release_date = models.DateTimeField(_("Data de Lançamento Efetiva"), null=True, blank=True, db_index=True)
    override_new_badge_settings = models.BooleanField(default=False, verbose_name=_("Sobrescrever Config. Global do Badge 'Novo'?"), help_text=_("Marque para definir manualmente o status/aparência do badge 'Novo' para ESTE capítulo, ignorando as configurações globais."))
    force_show_new_badge = models.BooleanField(default=False, verbose_name=_("Forçar Exibição do Badge 'Novo'?"), help_text=_("Se 'Sobrescrever' estiver marcado, esta opção força a exibição do badge. Usa texto/imagem global se os campos abaixo estiverem vazios."))
    manual_badge_text = models.CharField(max_length=20, blank=True, verbose_name=_("Texto Manual do Badge (Opcional)"), help_text=_("Texto específico para o badge deste capítulo. Se vazio e 'Forçar Exibição' estiver marcado, usará o texto global."))
    manual_badge_image = models.ForeignKey('wagtailimages.Image', null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name=_("Imagem/GIF Manual do Badge (Opcional)"), help_text=_("Imagem específica para o badge deste capítulo. Substitui o texto manual e a imagem global se definida."))
    views = models.PositiveIntegerField(_("Visualizações"), default=0, editable=False, help_text=_("Número de vezes que este capítulo foi visualizado."))
    search_fields = []
    def get_url(self, *args, **kwargs):
        manga_page = self.get_parent().specific
        return reverse('manga:chapter_reader', kwargs={'manga_slug': manga_page.slug, 'chapter_slug': self.slug})
    @property
    def is_effectively_vip(self):
        return self.get_vip_status().get('is_blocked', False)
    def get_vip_status(self):
        status = {'is_blocked': False, 'unlock_date': None, 'time_remaining': None}
        parent_manga = self.get_parent().specific
        if not isinstance(parent_manga, MangaPage):
            return status
        if parent_manga.chapters_are_vip:
            status['is_blocked'] = True
            return status
        if not parent_manga.default_chapters_are_vip and not self.is_vip:
            return status
        vip_limit = parent_manga.recent_vip_chapters_count
        if vip_limit <= 0:
            if self.is_vip: status['is_blocked'] = True
            return status
        try:
            all_chapters = parent_manga.get_chapters()
            current_chapter_index = -1
            for i, chap in enumerate(all_chapters):
                if chap.pk == self.pk:
                    current_chapter_index = i
                    break
            if current_chapter_index == -1 or current_chapter_index >= vip_limit:
                if self.is_vip: status['is_blocked'] = True
                return status
            tier_size = parent_manga.vip_tier_size if parent_manga.vip_tier_size > 0 else 1
            base_days = parent_manga.vip_base_release_days
            decrease_days = parent_manga.vip_days_decrease_per_tier
            tier_index = current_chapter_index // tier_size
            wait_days = base_days - (tier_index * decrease_days)
            wait_days = max(0, wait_days)
            if wait_days == 0:
                return status
            release_date = self.release_date_or_published
            if not release_date:
                status['is_blocked'] = True
                return status
            unlock_date = release_date + timezone.timedelta(days=wait_days)
            now = timezone.now()
            if now < unlock_date:
                status['is_blocked'] = True
                status['unlock_date'] = unlock_date
                status['time_remaining'] = unlock_date - now
            return status
        except Exception:
            if self.is_vip or parent_manga.default_chapters_are_vip: status['is_blocked'] = True
            return status
    @property
    def display_views(self):
        return self.views
    def _get_numerical_sort_key(self):
        num_str = str(self.chapter_number).strip().lower()
        if not num_str: return (float('inf'), float('inf'))
        num_str_cleaned = num_str.replace('capitulo', '').replace('cap.', '').replace('ch.', '').strip()
        match = re.match(r"(\d+)(?:[\.,](\d+))?(.*)", num_str_cleaned)
        if match:
            try:
                main_part_val = int(match.group(1))
                sub_part_val = int(match.group(2)) if match.group(2) else 0
                return (main_part_val, sub_part_val)
            except (ValueError, TypeError):
                return (float('inf'), self.chapter_number.lower())
        else:
            if "prólogo" in num_str or "prologue" in num_str: return (float('-inf'), 0)
            if "epílogo" in num_str or "epilogue" in num_str: return (float('inf'), float('inf')-1)
            return (float('inf'), self.chapter_number.lower())
    @property
    def get_thumbnail(self):
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail
        parent_page = self.get_parent().specific if self.get_parent() else None
        if isinstance(parent_page, MangaPage) and parent_page.cover:
            return parent_page.cover
        if GlobalSettings:
            try:
                site_settings = GlobalSettings.for_site(self.get_site()) if hasattr(GlobalSettings, 'for_site') and self.get_site() else GlobalSettings.objects.first()
                if site_settings and hasattr(site_settings, 'logo') and site_settings.logo:
                    return site_settings.logo
            except Exception:
                pass
        return None
    @property
    def is_wagtail_thumbnail(self):
        thumb = self.get_thumbnail
        return thumb and isinstance(thumb, WagtailImage)
    @property
    def is_standard_thumbnail(self):
        thumb = self.get_thumbnail
        return thumb and hasattr(thumb, 'url') and not isinstance(thumb, WagtailImage)
    def get_badge_info(self):
        badge_info = {'show': False, 'text': '', 'image_url': None}
        gs = None
        if GlobalSettings:
            try:
                current_site = self.get_site()
                gs = GlobalSettings.for_site(current_site) if current_site and hasattr(GlobalSettings, 'for_site') else GlobalSettings.objects.first()
            except Exception:
                gs = GlobalSettings.objects.first() if GlobalSettings.objects.exists() else None
        if self.override_new_badge_settings:
            if self.force_show_new_badge:
                badge_info['show'] = True
                if self.manual_badge_image:
                    badge_info['image_url'] = self.manual_badge_image.get_rendition('original').url
                elif self.manual_badge_text:
                    badge_info['text'] = self.manual_badge_text
                elif gs and hasattr(gs, 'new_chapter_badge_image') and gs.new_chapter_badge_image:
                    badge_info['image_url'] = gs.new_chapter_badge_image.get_rendition('original').url
                elif gs and hasattr(gs, 'new_chapter_badge_text') and gs.new_chapter_badge_text:
                    badge_info['text'] = gs.new_chapter_badge_text
                elif not badge_info['image_url'] and not badge_info['text']:
                    badge_info['text'] = _("NOVO!") 
            return badge_info
        if not self.release_date_or_published:
            return badge_info
        days_limit = 2
        global_badge_text_to_use = _("NOVO!")
        global_badge_image_url_to_use = None
        if gs:
            if hasattr(gs, 'new_chapter_days_threshold') and gs.new_chapter_days_threshold is not None:
                days_limit = gs.new_chapter_days_threshold
            if hasattr(gs, 'new_chapter_badge_text') and gs.new_chapter_badge_text:
                global_badge_text_to_use = gs.new_chapter_badge_text
            if hasattr(gs, 'new_chapter_badge_image') and gs.new_chapter_badge_image:
                try:
                    global_badge_image_url_to_use = gs.new_chapter_badge_image.get_rendition('original').url
                except Exception:
                    global_badge_image_url_to_use = None
        time_threshold = timezone.now() - timezone.timedelta(days=days_limit)
        if self.release_date_or_published > time_threshold:
            if global_badge_image_url_to_use or global_badge_text_to_use:
                badge_info['show'] = True
                if global_badge_image_url_to_use:
                    badge_info['image_url'] = global_badge_image_url_to_use
                elif global_badge_text_to_use: 
                    badge_info['text'] = global_badge_text_to_use
        return badge_info
    content_panels = Page.content_panels + [
        FieldRowPanel([FieldPanel('chapter_number', classname="col8"), FieldPanel('is_vip', classname="col4")]),
        FieldPanel('thumbnail'),
        FieldPanel('background_music'),
        FieldPanel('release_date'),
        MultiFieldPanel([
            FieldPanel('override_new_badge_settings'),
            FieldPanel('force_show_new_badge'),
            FieldPanel('manual_badge_text'),
            FieldPanel('manual_badge_image'),
        ], heading=_("Configurações Manuais do Badge 'Novo Capítulo'"), classname="collapsible collapsed"),
        InlinePanel('chapter_images', heading=_("Fatias de Imagem Criptografadas"), label=_("Fatia Criptografada")),
    ]
    parent_page_types = ['manga.MangaPage']
    subpage_types = []
    api_fields = [
        APIField('chapter_number'), APIField('is_vip'), APIField('thumbnail'),
        APIField('background_music'), APIField('release_date'), APIField('chapter_images'), APIField('_get_numerical_sort_key'),
        APIField('get_thumbnail'), APIField('get_badge_info'), APIField('views'),
        APIField('is_effectively_vip'), APIField('get_vip_status'),
    ]
    class Meta:
        verbose_name = _("Página de Capítulo")
        verbose_name_plural = _("Páginas de Capítulo")
        ordering = ['-release_date', '-path']
    def save(self, *args, **kwargs):
        parent_page = self.get_parent().specific
        if self.pk is None and parent_page and hasattr(parent_page, 'default_chapters_are_vip'):
            self.is_vip = parent_page.default_chapters_are_vip
        if not self.title:
            parent_title_text = _("Obra")
            try:
                if parent_page and hasattr(parent_page, 'title') and parent_page.title:
                    parent_title_text = parent_page.title
            except Exception:
                pass
            self.title = f"{parent_title_text} - {_('Capítulo')} {self.chapter_number}"
        if self.chapter_number:
            new_slug = slugify(str(self.chapter_number).replace('.', '-'))
            if not self.slug or self.slug != new_slug:
                self.slug = new_slug if new_slug else f"cap-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        elif not self.slug:
            self.slug = f"capitulo-sem-numero-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        super().save(*args, **kwargs)
    @property
    def release_date_or_published(self):
        return self.release_date or self.first_published_at
    def get_context(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            ReadingHistory.objects.update_or_create(user=request.user, chapter=self)
        if request.user and not request.user.is_superuser and not request.user.is_staff:
            MangaChapterPage.objects.filter(pk=self.pk).update(views=F('views') + 1)
            self.refresh_from_db(fields=['views'])
        context = super().get_context(request, *args, **kwargs)
        context['current_chapter_views'] = self.views 
        parent_page = self.get_parent().specific if self.get_parent() else None
        next_chapter_direct = None
        prev_chapter_direct = None
        if isinstance(parent_page, MangaPage):
            all_siblings_qs = MangaChapterPage.objects.live().public().child_of(parent_page).specific()
            ordered_siblings_for_nav = sorted(
                list(all_siblings_qs),
                 key=lambda chap: (
                    chap._get_numerical_sort_key(),
                    -(chap.release_date_or_published or timezone.datetime.min.replace(tzinfo=timezone.utc)).timestamp() if chap.release_date_or_published else float('-inf'),
                    chap.title.lower()
                )
            )
            current_idx_direct = -1
            for i, s_chap in enumerate(ordered_siblings_for_nav):
                if s_chap.pk == self.pk:
                    current_idx_direct = i
                    break
            if current_idx_direct != -1:
                if current_idx_direct < len(ordered_siblings_for_nav) - 1:
                    next_chapter_direct = ordered_siblings_for_nav[current_idx_direct + 1]
                if current_idx_direct > 0:
                    prev_chapter_direct = ordered_siblings_for_nav[current_idx_direct - 1]
        else:
            pass
        context.update({
            'manga': parent_page,
            'chapter': self,
            'chapter_image_ids': list(self.chapter_images.values_list('id', flat=True).order_by('sort_order')),
            'next_chapter': next_chapter_direct,
            'prev_chapter': prev_chapter_direct,
            'release_date_display': self.release_date_or_published,
        })
        return context

class MangaComment(models.Model):
    page = ParentalKey(Page, on_delete=models.CASCADE, related_name='manga_comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_manga_comments")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    text = models.TextField(_("Comentário"), max_length=3000)
    image = models.ImageField(_("Imagem Anexada"), upload_to='comment_images/%Y/%m/', blank=True, null=True)
    is_spoiler = models.BooleanField(_("É Spoiler?"), default=False)
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)
    def __str__(self):
        preview = (self.text[:50] + '...') if len(self.text) > 50 else self.text
        try: 
            page_title_str = self.page.specific.title if self.page and hasattr(self.page, 'specific') else _("Página Desconhecida")
        except AttributeError:
            page_title_str = _("Página Removida")
        user_name_str = self.user.get_username() if self.user else _("Usuário Desconhecido")
        return f"{_('Comentário de')} {user_name_str} {_('em')} '{page_title_str}': '{preview}'"
    class Meta:
        verbose_name = _("Comentário de Mangá")
        verbose_name_plural = _("Comentários de Mangá")
        ordering = ['created_at']

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='manga_favorites', verbose_name=_("Usuário"))
    manga = models.ForeignKey('manga.MangaPage', on_delete=models.CASCADE, related_name='favorited_by', verbose_name=_("Mangá"))
    favorited_at = models.DateTimeField(default=timezone.now, verbose_name=_("Favoritado em"))
    class Meta:
        unique_together = ('user', 'manga')
        ordering = ['-favorited_at']
        verbose_name = _("Favorito de Mangá")
        verbose_name_plural = _("Favoritos de Mangá")
    def __str__(self):
        user_name_str = self.user.username if self.user else _("Usuário Desconhecido")
        manga_title_str = self.manga.title if self.manga else _("Mangá Desconhecido")
        return f"{user_name_str} {_('favoritou')} '{manga_title_str}'"

class ReadingHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reading_history', verbose_name=_("Usuário"))
    chapter = models.ForeignKey('manga.MangaChapterPage', on_delete=models.CASCADE, related_name='read_by_users', verbose_name=_("Capítulo Lido"))
    read_at = models.DateTimeField(_("Lido em"), auto_now=True, db_index=True)
    class Meta:
        unique_together = ('user', 'chapter')
        ordering = ['-read_at']
        verbose_name = _("Registro de Histórico")
        verbose_name_plural = _("Registros de Histórico")
    def __str__(self):
        user_name = self.user.get_username() if self.user else "Usuário Desconhecido"
        chapter_title = self.chapter.title if self.chapter else "Capítulo Desconhecido"
        return f"{user_name} leu '{chapter_title}'"