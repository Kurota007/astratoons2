# Arquivo: home/models.py
from django.db import models
from django.db.models import OuterRef, Subquery, Value, CharField
from wagtail.models import Page
import operator
import logging

logger = logging.getLogger(__name__)

try:
    from manga.models import MangaPage, MangaChapterPage
    MANGA_MODELS_IMPORTED_SUCCESSFULLY = True
except ImportError: MangaPage, MangaChapterPage, MANGA_MODELS_IMPORTED_SUCCESSFULLY = None, None, False
try:
    from novels.models import NovelPage, NovelChapterPage
    NOVEL_MODELS_IMPORTED_SUCCESSFULLY = True
except ImportError: NovelPage, NovelChapterPage, NOVEL_MODELS_IMPORTED_SUCCESSFULLY = None, None, False

class HomePage(Page):
    max_count = 1
    template = "home/home_page.html"
    subpage_types = ['manga.MangaPage', 'novels.NovelPage', 'wagtailcore.Page']

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        all_latest_items = []
        popular_mangas_list = None
        
        if MANGA_MODELS_IMPORTED_SUCCESSFULLY:
            try:
                latest_chapter_publish_date_subquery = MangaChapterPage.objects.filter(
                    path__startswith=OuterRef('path'),
                    depth=OuterRef('depth') + 1,
                    live=True,
                    first_published_at__isnull=False
                ).order_by('-first_published_at').values('first_published_at')[:1]

                latest_mangas = (
                    MangaPage.objects.visible_for(request.user)
                    .annotate(
                        latest_activity_date=Subquery(
                            latest_chapter_publish_date_subquery,
                            output_field=models.DateTimeField(null=True)
                        ),
                        item_type=Value('manga', output_field=CharField())
                    )
                    .filter(latest_activity_date__isnull=False)
                )
                all_latest_items.extend(list(latest_mangas))
            except Exception as e:
                logger.error(f"HomePage: Erro ao buscar Últimos Lançamentos de MANGÁS: {e}", exc_info=True)
        
        if NOVEL_MODELS_IMPORTED_SUCCESSFULLY:
            try:
                latest_novel_chapter_date_subquery = NovelChapterPage.objects.filter(
                    path__startswith=OuterRef('path'),
                    depth=OuterRef('depth') + 1,
                    live=True,
                    first_published_at__isnull=False
                ).order_by('-first_published_at').values('first_published_at')[:1]

                base_queryset_novels = getattr(NovelPage, 'objects', NovelPage.objects)
                visible_novels_qs = base_queryset_novels.visible_for(request.user) if hasattr(base_queryset_novels, 'visible_for') else base_queryset_novels.live().public()

                latest_novels = (
                    visible_novels_qs
                    .annotate(
                        latest_activity_date=Subquery(
                            latest_novel_chapter_date_subquery,
                            output_field=models.DateTimeField(null=True)
                        ),
                        item_type=Value('novel', output_field=CharField())
                    )
                    .filter(latest_activity_date__isnull=False)
                )
                all_latest_items.extend(list(latest_novels))
            except Exception as e:
                logger.error(f"HomePage: Erro ao buscar Últimos Lançamentos de NOVELS: {e}", exc_info=True)

        if all_latest_items:
            sorted_items = sorted(all_latest_items, key=operator.attrgetter('latest_activity_date'), reverse=True)
            context['latest_items'] = sorted_items[:12]
            context['has_more_items'] = len(sorted_items) > 12
        else:
            context['latest_items'] = []
            context['has_more_items'] = False
            
        if MANGA_MODELS_IMPORTED_SUCCESSFULLY:
            try:
                base_queryset_mangas = MangaPage.objects.visible_for(request.user)
                if hasattr(MangaPage, 'views_count'):
                    popular_mangas_list = base_queryset_mangas.order_by('-views_count')[:6]
                else:
                    popular_mangas_list = base_queryset_mangas.order_by('-first_published_at')[:6]
            except Exception as e_popular:
                logger.error(f"HomePage: Erro ao buscar Mais Vistos: {e_popular}", exc_info=True)
                popular_mangas_list = None
        
        context['popular_mangas'] = popular_mangas_list
        return context

    class Meta:
        verbose_name = "Página Inicial"