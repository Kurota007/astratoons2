# manga/apps.py

from django.apps import AppConfig

class MangaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'manga'
    verbose_name = "Gerenciamento de Mangás"

    def ready(self):
        # A importação correta deve ser 'manga.signals'
        import manga.signals