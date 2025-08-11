# novels/models.py

from django.db import models
from django.db.models import F
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from modelcluster.fields import ParentalKey
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase

from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, FieldRowPanel
from wagtail.search import index

def novel_cover_path(instance, filename):
    if instance.slug:
        page_identifier = instance.slug
    elif instance.title:
        page_identifier = slugify(instance.title)
    else:
        page_identifier = f"novel-{instance.pk or 'new'}"
    return f'novels/covers/{page_identifier}/{filename}'


class NovelGenreTag(TaggedItemBase):
    content_object = ParentalKey(
        'novels.NovelPage',
        related_name='genre_tags',
        on_delete=models.CASCADE
    )
    class Meta:
        verbose_name = _("Gênero da Novel")
        verbose_name_plural = _("Gêneros da Novel")

class NovelPage(Page):
    author_name = models.CharField(_("Nome do Autor(es)"), max_length=255, blank=True)
    cover_image = models.ForeignKey(
        'wagtailimages.Image',
        verbose_name=_("Capa da Novel"),
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )
    genres = ClusterTaggableManager(
        verbose_name=_("Gêneros"),
        through=NovelGenreTag,
        blank=True
    )
    synopsis = RichTextField(_("Sinopse"), features=['bold', 'italic', 'link'], blank=True)

    discord_series_role_id = models.CharField(
        _("ID do Cargo no Discord (Notificações)"),
        max_length=30,
        blank=True,
        null=True,
        help_text=_("Opcional. ID do cargo do Discord a ser mencionado quando novos capítulos desta obra forem lançados.")
    )

    class NovelStatusChoices(models.TextChoices):
        DRAFT = 'DR', _('Rascunho')
        ONGOING = 'OG', _('Em Andamento')
        COMPLETED = 'CP', _('Concluída')
        HIATUS = 'HT', _('Hiato')
        CANCELLED = 'CL', _('Cancelada')

    status = models.CharField(
        _("Status"),
        max_length=2,
        choices=NovelStatusChoices.choices,
        default=NovelStatusChoices.ONGOING
    )
    
    # --- EDIÇÃO AQUI: Adiciona o campo de controle VIP para a obra ---
    default_chapters_are_vip = models.BooleanField(
        _("Capítulos Novos são VIP por Padrão?"),
        default=False,
        help_text=_("Se marcado, novos capítulos criados para esta novel serão marcados como VIP automaticamente.")
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('author_name'),
            FieldPanel('cover_image'),
            FieldPanel('genres'),
            FieldRowPanel([
                FieldPanel('status', classname="col6"),
                FieldPanel('default_chapters_are_vip', classname="col6"),
            ]),
            FieldPanel('discord_series_role_id'),
        ], heading=_("Informações da Novel")),
        FieldPanel('synopsis'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('author_name'),
        index.SearchField('synopsis'),
        index.RelatedFields('genres', [
            index.SearchField('name', partial_match=True, boost=1.1),
            index.FilterField('slug')
        ])
    ]

    parent_page_types = ['home.HomePage']
    subpage_types = ['novels.NovelChapterPage']
    
    @property
    def cover(self):
        return self.cover_image

    def get_chapters(self):
        # Esta função pode precisar ser ajustada no futuro para lidar com a lógica de acesso VIP
        all_chapters_qs = NovelChapterPage.objects.child_of(self).live().public().specific()
        all_chapters_list = list(all_chapters_qs)
        chapters_sorted_list = sorted(
            all_chapters_list,
            key=lambda chap: chap.chapter_number_sortable
        )
        chapters_sorted_list.reverse()
        return chapters_sorted_list

    def get_recent_chapters(self, limit=3):
        all_sorted_chapters = self.get_chapters()
        return all_sorted_chapters[:limit]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        all_chapters_list = self.get_chapters()
        
        search_query_val = request.GET.get('q_chapter', '').strip()
        context['search_query'] = search_query_val
        if search_query_val:
            filtered_list = [
                chap for chap in all_chapters_list 
                if search_query_val.lower() in chap.chapter_display_title.lower()
            ]
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
        
        is_following = False
        if request.user.is_authenticated:
            # Assumindo que o modelo Favorite existe
            is_following = Favorite.objects.filter(user=request.user, novel=self).exists()
        
        context['is_following'] = is_following
        context['followers_count'] = self.favorited_by.count()
        context['chapter_count'] = len(all_chapters_list)

        return context

    class Meta:
        verbose_name = _("Página de Novel")
        verbose_name_plural = _("Páginas de Novel")


class NovelChapterPage(Page):
    chapter_display_title = models.CharField(
        _("Título de Exibição do Capítulo"), max_length=255,
        help_text=_("Ex: 'Capítulo 1: O Despertar', 'Prólogo'"), default=""
    )
    chapter_number_sortable = models.FloatField(
        _("Número para Ordenação"), default=0.0,
        help_text=_("Ex: 1.0, 1.5, 2.0. Usado para ordenar capítulos.")
    )
    main_content = RichTextField(
        _("Conteúdo Principal do Capítulo"),
        features=['h2', 'h3', 'h4', 'bold', 'italic', 'link', 'ol', 'ul', 'hr', 'blockquote'],
        default=""
    )
    release_date = models.DateTimeField(
        _("Data de Publicação/Lançamento"), default=timezone.now, db_index=True, blank=True, null=True
    )
    views = models.PositiveIntegerField(
        _("Visualizações"), default=0, editable=False,
        help_text=_("Número de vezes que este capítulo foi visualizado.")
    )
    cover = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("Thumbnail Personalizada (Opcional)"),
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    
    # --- EDIÇÃO AQUI: Adiciona o campo de controle VIP para o capítulo ---
    is_vip = models.BooleanField(
        _("Capítulo VIP?"),
        default=False,
        help_text=_("Marque se este capítulo for exclusivo para assinantes VIP.")
    )

    @property
    def get_thumbnail(self):
        if self.cover:
            return self.cover
        parent_page = self.get_parent().specific if self.get_parent() else None
        if parent_page and hasattr(parent_page, 'cover_image'):
            return parent_page.cover_image
        return None

    content_panels = Page.content_panels + [
        FieldRowPanel([
            FieldPanel('chapter_display_title', classname="col8"),
            FieldPanel('is_vip', classname="col4"),
        ]),
        FieldPanel('chapter_number_sortable'),
        FieldPanel('release_date'),
        FieldPanel('cover'),
        FieldPanel('main_content'),
    ]

    settings_panels = Page.settings_panels + [
        FieldPanel('views', read_only=True),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('chapter_display_title'),
        index.SearchField('main_content'),
    ]

    parent_page_types = ['novels.NovelPage']
    subpage_types = []

    @property
    def chapter_number(self):
        if self.chapter_number_sortable.is_integer():
            return int(self.chapter_number_sortable)
        return self.chapter_number_sortable

    def get_badge_info(self):
        if self.first_published_at and (timezone.now() - self.first_published_at).days < 3:
            return {'show': True, 'text': 'NOVO!'}
        return {'show': False}

    @property
    def chapter_number_display(self):
        return self.chapter_display_title

    class Meta:
        verbose_name = _("Página de Capítulo de Novel")
        verbose_name_plural = _("Páginas de Capítulo de Novel")
        ordering = ['-chapter_number_sortable']

    def save(self, *args, **kwargs):
        # Herda o status VIP da página pai se for a primeira vez que está sendo salvo
        parent_page = self.get_parent().specific
        if self.pk is None and parent_page and hasattr(parent_page, 'default_chapters_are_vip'):
            self.is_vip = parent_page.default_chapters_are_vip

        if not self.title and self.chapter_display_title:
            if parent_page and hasattr(parent_page, 'title'):
                self.title = f"{parent_page.title} - {self.chapter_display_title}"
            else:
                self.title = self.chapter_display_title
        super().save(*args, **kwargs)

    def serve(self, request, *args, **kwargs):
        # A lógica de verificação VIP será adicionada aqui no futuro
        if not request.user.is_staff:
            session_key = f'viewed_novel_chapter_{self.pk}'
            if not request.session.get(session_key, False):
                NovelChapterPage.objects.filter(pk=self.pk).update(views=F('views') + 1)
                request.session[session_key] = True
        return super().serve(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        parent_novel_page = self.get_parent().specific if self.get_parent() else None
        context['novel'] = parent_novel_page
        context['chapter'] = self
        return context


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='novel_favorites', verbose_name=_("Usuário")
    )
    novel = models.ForeignKey(
        'novels.NovelPage', on_delete=models.CASCADE,
        related_name='favorited_by', verbose_name=_("Favorito")
    )
    favorited_at = models.DateTimeField(
        default=timezone.now, verbose_name=_("Favoritado em")
    )

    class Meta:
        unique_together = ('user', 'novel')
        ordering = ['-favorited_at']
        verbose_name = _("Favorito")
        verbose_name_plural = _("Favoritos")

    def __str__(self):
        return f"{self.user.username} favoritou '{self.novel.title}'"