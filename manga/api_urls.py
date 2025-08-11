# manga/api_urls.py

from django.urls import path
# Importar a nova view de lista junto com a de teste
from .views import TesteAPIView, MangaListAPIView 

app_name = 'manga_api'

urlpatterns = [
    # URL de teste que já fizemos
    # Acessível em: /api/manga/teste/
    path('teste/', TesteAPIView.as_view(), name='api_teste'),

    # Adicionamos esta nova linha para a lista de mangás
    # Acessível em: /api/manga/lista/
    path('lista/', MangaListAPIView.as_view(), name='api_lista_mangas'),
]