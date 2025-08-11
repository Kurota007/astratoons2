# Em comments/apps.py

from django.apps import AppConfig

class CommentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'comments'

    def ready(self):
        # A única importação que deve estar aqui é a dos signals.
        # NÃO PODE ter 'from .models import ...' no topo deste arquivo.
        import comments.signals