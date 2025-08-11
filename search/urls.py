# search/urls.py (VERSÃO CORRIGIDA E FINAL)

from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    # CORREÇÃO: Aponta para 'views.custom_search' em vez de 'views.search_view'
    path('', views.custom_search, name='custom_search'),
    
    # Esta linha já estava correta
    path('live-search/', views.live_search_view, name='live_search'),
]