# core/context_processors.py

from manga.models import Genre

def menu_context(request):
    """
    Esta função busca os gêneros e os envia para todos os templates do site,
    permitindo que o menu seja construído.
    """
    # Busca todos os gêneros do banco de dados
    genres = Genre.objects.all()

    # Disponibiliza a lista de gêneros na variável 'menu_genres'
    return {
        'menu_genres': genres
    }