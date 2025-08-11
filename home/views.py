from django.template.loader import render_to_string
from django.http import JsonResponse
import operator
from django.db.models import OuterRef, Subquery, Value, CharField, DateTimeField

try:
    from manga.models import MangaPage, MangaChapterPage
    MANGA_MODELS_IMPORTED_SUCCESSFULLY = True
except ImportError: MangaPage, MangaChapterPage, MANGA_MODELS_IMPORTED_SUCCESSFULLY = None, None, False
try:
    from novels.models import NovelPage, NovelChapterPage
    NOVEL_MODELS_IMPORTED_SUCCESSFULLY = True
except ImportError: NovelPage, NovelChapterPage, NOVEL_MODELS_IMPORTED_SUCCESSFULLY = None, None, False

def load_more_releases(request):
    page_number = int(request.GET.get('page', 2))
    items_per_page = 12
    all_items = []

    if MANGA_MODELS_IMPORTED_SUCCESSFULLY:
        latest_chapter_publish_date_subquery = MangaChapterPage.objects.filter(
            path__startswith=OuterRef('path'),
            depth=OuterRef('depth') + 1,
            live=True,
            first_published_at__isnull=False
        ).order_by('-first_published_at').values('first_published_at')[:1]
        latest_mangas = MangaPage.objects.visible_for(request.user).annotate(
            latest_activity_date=Subquery(latest_chapter_publish_date_subquery, output_field=DateTimeField(null=True)),
            item_type=Value('manga', output_field=CharField())
        ).filter(latest_activity_date__isnull=False)
        all_items.extend(list(latest_mangas))

    if NOVEL_MODELS_IMPORTED_SUCCESSFULLY:
        latest_novel_chapter_date_subquery = NovelChapterPage.objects.filter(
            path__startswith=OuterRef('path'),
            depth=OuterRef('depth') + 1,
            live=True,
            first_published_at__isnull=False
        ).order_by('-first_published_at').values('first_published_at')[:1]
        base_queryset_novels = getattr(NovelPage, 'objects', NovelPage.objects)
        visible_novels_qs = base_queryset_novels.visible_for(request.user) if hasattr(base_queryset_novels, 'visible_for') else base_queryset_novels.live().public()
        latest_novels = visible_novels_qs.annotate(
            latest_activity_date=Subquery(latest_novel_chapter_date_subquery, output_field=DateTimeField(null=True)),
            item_type=Value('novel', output_field=CharField())
        ).filter(latest_activity_date__isnull=False)
        all_items.extend(list(latest_novels))
        
    sorted_items = sorted(all_items, key=operator.attrgetter('latest_activity_date'), reverse=True)
    
    start_index = (page_number - 1) * items_per_page
    end_index = start_index + items_per_page
    
    page_items = sorted_items[start_index:end_index]
    has_next = len(sorted_items) > end_index

    html = render_to_string(
        'includes/manga_card_list.html', 
        {'mangas_to_load': page_items}
    )
    
    return JsonResponse({'html': html, 'has_next': has_next})