# ~/astratoons/search/views.py

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse
from django.http import JsonResponse

from wagtail.models import Page
from wagtail.contrib.search_promotions.models import Query

from manga.models import MangaChapterPage
from novels.models import NovelChapterPage


def live_search_view(request):
    search_query = request.GET.get('q', None)
    results = []

    if search_query:
        # Exclui páginas de capítulo da busca para mostrar apenas a obra principal
        manga_chapter_pks = MangaChapterPage.objects.values_list('pk', flat=True)
        novel_chapter_pks = NovelChapterPage.objects.values_list('pk', flat=True)
        all_chapter_pks = list(manga_chapter_pks) + list(novel_chapter_pks)

        pages_to_search = Page.objects.live().public().exclude(pk__in=all_chapter_pks)
        
        # A ordem .specific().search() é importante para ter acesso aos campos do modelo filho
        search_results = pages_to_search.specific().search(search_query)

        for page in search_results[:5]: # Limita a 5 resultados para a busca ao vivo
            cover_url = ''
            if hasattr(page, 'cover') and page.cover:
                # Trata tanto imagens do Wagtail quanto ImageFields padrão
                if hasattr(page.cover, 'get_rendition'):
                    cover_url = page.cover.get_rendition('fill-80x112').url
                elif hasattr(page.cover, 'url'):
                    cover_url = page.cover.url

            chapter_count = 0
            if hasattr(page, 'get_chapters') and callable(page.get_chapters):
                chapter_count = len(page.get_chapters())

            results.append({
                'title': page.title,
                'url': page.get_url(),
                'cover_url': cover_url,
                'chapters_text': f"{chapter_count} capítulos"
            })

    return JsonResponse({'results': results})


def custom_search(request):
    search_query = request.GET.get("query", None)
    page = request.GET.get("page", 1)

    search_results = Page.objects.none()

    if search_query:
        # Mesma lógica para excluir capítulos da busca principal
        manga_chapter_pks = MangaChapterPage.objects.values_list('pk', flat=True)
        novel_chapter_pks = NovelChapterPage.objects.values_list('pk', flat=True)
        all_chapter_pks = list(manga_chapter_pks) + list(novel_chapter_pks)

        pages_to_search = Page.objects.live().public().exclude(pk__in=all_chapter_pks)
        search_results = pages_to_search.search(search_query)
        Query.get(search_query).add_hit()

    # Paginação dos resultados
    paginator = Paginator(search_results, 10)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return TemplateResponse(
        request,
        "search/search.html", # Seu template de resultados
        {
            "search_query": search_query,
            "search_results": search_results,
        },
    )