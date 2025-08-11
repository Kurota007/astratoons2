# core/urls.py
from django.urls import path
from home import views as home_views
from . import api_views  # <-- ADICIONE ESTA LINHA PARA IMPORTAR DO APP 'core'

app_name = 'core'

urlpatterns = [
    path('load-more-releases/', home_views.load_more_releases, name='load_more_releases'),
    # --- URL PARA A API DE REAÇÕES ---
    path('api/toggle-reaction/', api_views.toggle_reaction, name='api_toggle_reaction'),
]