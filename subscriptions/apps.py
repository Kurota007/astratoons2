# subscriptions/apps.py

from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'subscriptions'

    def ready(self):
        """
        Esta função é executada quando o Django inicia.
        É o local recomendado para importar e registrar os sinais (signals).
        """
        # Importa o arquivo signals.py para conectar os receivers.
        import subscriptions.signals