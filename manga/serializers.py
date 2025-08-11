# manga/serializers.py

from rest_framework import serializers
from .models import MangaPage

class MangaListSerializer(serializers.ModelSerializer):
    """
    Um "tradutor" que converte os dados de um MangaPage para um formato JSON
    otimizado para a lista do aplicativo.
    """
    
    # Campo customizado para gerar a URL completa da capa.
    # O aplicativo precisa do endereço completo da imagem para exibi-la.
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = MangaPage
        
        # Lista dos campos que queremos enviar para o aplicativo.
        # Mantemos simples para a lista ser rápida.
        fields = [
            'id', 
            'title', 
            'cover_url'
        ]

    def get_cover_url(self, manga_page_obj):
        """
        Esta função é responsável por criar a URL completa da capa.
        Ela é chamada automaticamente pelo Serializer para o campo 'cover_url'.
        
        'manga_page_obj' é a instância do MangaPage que está sendo processada.
        """
        # Primeiro, verifica se o mangá tem uma capa cadastrada.
        if manga_page_obj.cover:
            # Pega a requisição original para saber o domínio (ex: http://127.0.0.1:8000)
            request = self.context.get('request')

            # Pede para o Wagtail criar uma versão da imagem com 300px de largura e 450px de altura.
            # Isso é ótimo para performance, pois não envia a imagem gigante original.
            rendition = manga_page_obj.cover.get_rendition('fill-300x450')

            # Se conseguimos pegar a requisição, construímos a URL completa.
            if request is not None:
                return request.build_absolute_uri(rendition.url)
            
            # Caso contrário, retorna apenas a URL relativa (menos ideal, mas funciona).
            return rendition.url
        
        # Se o mangá não tiver capa, retorna nulo.
        return None