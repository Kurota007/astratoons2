# accounts/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp # Necessário para criar o objeto SocialApp em memória
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist # Embora não usemos mais .get() que levanta isso para SocialProviderSettings
import logging

# Tenta importar o modelo de settings do Wagtail
try:
    from core.models import SocialProviderSettings
except ImportError:
    # Loga um aviso se o modelo não puder ser importado
    # O adapter ainda tentará o fallback para o SocialApp padrão do allauth.
    logging.getLogger(__name__).warning(
        "O modelo 'SocialProviderSettings' do app 'core' não foi encontrado. "
        "O CustomSocialAccountAdapter fará fallback para o SocialApp padrão do allauth."
    )
    SocialProviderSettings = None # Define como None para verificações condicionais

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adaptador social customizado que tenta buscar credenciais OAuth2
    primeiro do modelo SocialProviderSettings (configurações do Wagtail)
    e, como fallback, do modelo SocialApp padrão do django-allauth.
    """

    def get_app(self, request, provider, client_id=None, **kwargs):
        """
        Sobrescreve o método get_app para implementar a lógica de busca de credenciais.
        'client_id' aqui é um parâmetro opcional que o allauth pode passar,
        não necessariamente o que vamos usar se encontrarmos nos Wagtail Settings.
        """
        app_from_wagtail_settings = None # Armazenará o SocialApp criado a partir do Wagtail Settings

        # Determina o site atual. Necessário para o fallback para super().get_app()
        # e pode ser útil para logs ou lógicas futuras.
        current_site = Site.objects.get_current(request) if request else Site.objects.get(pk=settings.SITE_ID)
        logger.debug(
            f"CustomSocialAccountAdapter.get_app chamado para provider='{provider}', "
            f"site='{current_site.domain}'. "
            f"Client ID passado pelo allauth (se houver): '{client_id}'"
        )

        # Passo 1: Tentar carregar do SocialProviderSettings (Wagtail)
        if SocialProviderSettings:
            logger.debug(f"Tentando carregar SocialProviderSettings (que é um BaseGenericSetting)...")
            try:
                settings_instance = SocialProviderSettings.load() # Para BaseGenericSetting
                logger.debug(f"SocialProviderSettings carregado: {settings_instance} (Tipo: {type(settings_instance)})")

                # Variáveis para armazenar as credenciais lidas do Wagtail
                provider_client_id_from_wagtail = None
                provider_secret_from_wagtail = None
                provider_name_for_app = provider # Nome padrão
                app_specific_settings_extra = {} # Configurações extras para o SocialApp

                # Lógica específica para cada provedor que você quer carregar do Wagtail Settings
                if provider == 'discord':
                    logger.debug(f"Processando provider 'discord' com settings_instance: {settings_instance}")
                    try:
                        provider_client_id_from_wagtail = settings_instance.discord_client_id
                        provider_secret_from_wagtail = settings_instance.discord_client_secret
                        # LOGS DETALHADOS PARA VERIFICAR OS VALORES LIDOS:
                        logger.info(f"  LIDO DO WAGTAIL SETTINGS - Discord Client ID: '{provider_client_id_from_wagtail}'")
                        # Loga apenas uma parte do segredo por segurança
                        secret_preview = provider_secret_from_wagtail[-6:] if provider_secret_from_wagtail and len(provider_secret_from_wagtail) > 5 else 'SEGREDO CURTO/VAZIO/NONE'
                        logger.info(f"  LIDO DO WAGTAIL SETTINGS - Discord Secret (final): '...{secret_preview}'")
                    except AttributeError as e:
                        logger.error(f"  AttributeError ao tentar ler discord_client_id/secret de SocialProviderSettings: {e}")
                        # Garante que as variáveis fiquem None se houver erro de atributo

                elif provider == 'google':
                    # Adicione lógica similar para o Google se você também o configura via Wagtail Settings
                    logger.debug(f"Processando provider 'google' com settings_instance: {settings_instance}")
                    try:
                        provider_client_id_from_wagtail = settings_instance.google_client_id
                        provider_secret_from_wagtail = settings_instance.google_client_secret
                        logger.info(f"  LIDO DO WAGTAIL SETTINGS - Google Client ID: '{provider_client_id_from_wagtail}'")
                        secret_preview = provider_secret_from_wagtail[-6:] if provider_secret_from_wagtail and len(provider_secret_from_wagtail) > 5 else 'SEGREDO CURTO/VAZIO/NONE'
                        logger.info(f"  LIDO DO WAGTAIL SETTINGS - Google Secret (final): '...{secret_preview}'")
                    except AttributeError as e:
                        logger.error(f"  AttributeError ao tentar ler google_client_id/secret de SocialProviderSettings: {e}")
                # Adicione outros 'elif provider == ...' para outros provedores se necessário

                # Se as credenciais foram encontradas no Wagtail Settings, crie um objeto SocialApp em memória
                if provider_client_id_from_wagtail and provider_secret_from_wagtail:
                    provider_name_for_app = f"{provider.capitalize()} (via Wagtail Settings)" # Nome mais descritivo
                    app_from_wagtail_settings = SocialApp(
                        provider=provider,
                        name="astraverselogin",
                        client_id=provider_client_id_from_wagtail,
                        secret=provider_secret_from_wagtail,
                        key="", # Geralmente não usado para OAuth2
                        settings=app_specific_settings_extra
                    )
                    # Adiciona o site ao objeto SocialApp em memória.
                    # Embora não seja salvo no DB, algumas partes do allauth podem esperar isso.
                    # app_from_wagtail_settings.sites.add(current_site) # Isso requer que o app seja salvo primeiro.
                                                                    # Para um objeto em memória, não é trivial.
                                                                    # Se allauth só precisa de client_id/secret, está ok.
                    logger.info(
                        f"SUCESSO AO USAR SocialProviderSettings: Criado SocialApp em memória para '{provider_name_for_app}'. "
                        f"Client ID usado (final): '...{provider_client_id_from_wagtail[-6:] if provider_client_id_from_wagtail else 'N/A'}'"
                    )
                # Log específico se as credenciais para o provider atual não foram populadas do Wagtail
                elif provider_client_id_from_wagtail is None and provider_secret_from_wagtail is None and provider in ['discord', 'google']: # Apenas para providers que tentamos carregar
                    logger.warning(
                        f"Credenciais para '{provider}' não foram encontradas ou os campos estão vazios em SocialProviderSettings. "
                        f"Tentando fallback para SocialApp DB."
                    )

            except AttributeError as e: # Erro se settings_instance for None ou não tiver os campos esperados
                logger.error(
                    f"Erro de atributo ao acessar/usar SocialProviderSettings para '{provider}' "
                    f"(provavelmente settings_instance é None ou o modelo/campo não existe como esperado): {e}. Tentando fallback.",
                    exc_info=True
                )
            except Exception as e: # Outros erros inesperados ao carregar/usar SocialProviderSettings
                logger.error(
                    f"Erro inesperado ao carregar ou usar SocialProviderSettings para '{provider}': {e}. "
                    f"Tentando fallback.",
                    exc_info=True
                )
        else:
            logger.info(
                "Modelo SocialProviderSettings (core.models) não disponível/importado. "
                "Pulando busca em Wagtail Settings, tentando fallback para SocialApp DB."
            )

        # Se um SocialApp foi criado com sucesso a partir do Wagtail Settings, retorne-o.
        if app_from_wagtail_settings and app_from_wagtail_settings.client_id and app_from_wagtail_settings.secret:
            logger.debug(f"Retornando SocialApp criado a partir do Wagtail Settings para '{provider}'.")
            return app_from_wagtail_settings

        # Passo 2: Fallback para o modelo SocialApp padrão do django-allauth (busca no DB)
        logger.debug(
            f"SocialApp para '{provider}' não foi criado/válido a partir do Wagtail Settings. "
            f"Tentando fallback para SocialApp padrão do DB..."
        )
        app_from_db = None
        try:
            # Chama o método original da classe pai para buscar no banco de dados.
            # Passa o 'client_id' que o allauth pode ter fornecido, caso seja relevante para o super().
            app_from_db = super().get_app(request, provider=provider, client_id=client_id, **kwargs)
            if app_from_db:
                logger.info(
                    f"Usando SocialApp padrão do DB para '{provider}' no site '{current_site.domain}'. "
                    f"Nome: '{app_from_db.name}', Client ID (final): '...{app_from_db.client_id[-6:] if app_from_db.client_id else 'N/A'}'"
                )
        except SocialApp.DoesNotExist:
            logger.warning(
                f"Nenhuma configuração SocialApp padrão do DB encontrada para '{provider}' no site '{current_site.domain}'."
            )
        except Exception as e:
            logger.error(
                f"Erro ao tentar fallback para SocialApp padrão do DB para '{provider}': {e}",
                exc_info=True
            )

        # Se um SocialApp foi encontrado no DB e é válido, retorne-o.
        if app_from_db and app_from_db.client_id and app_from_db.secret:
            logger.debug(f"Retornando SocialApp encontrado no DB para '{provider}'.")
            return app_from_db

        # Passo 3: Se nada foi encontrado, logue um erro crítico e retorne um SocialApp "dummy" inválido.
        # Isso fará com que o allauth mostre uma mensagem de erro ao usuário em vez de quebrar o site.
        logger.error(
            f"ERRO FINAL: Nenhuma credencial OAuth válida encontrada para o provider '{provider}' no site '{current_site.domain}' "
            f"(nem de SocialProviderSettings via Wagtail, nem de SocialApp via DB do allauth)."
            f"Verifique as configurações em Wagtail Admin -> Configurações -> Credenciais de Login Social E "
            f"Django Admin -> Social Accounts -> Social applications."
        )
        # Retornar um SocialApp "dummy" inválido para o allauth lidar com o erro graciosamente.
        return SocialApp(
            provider=provider,
            name=f"{provider.capitalize()} (NÃO CONFIGURADO!)",
            client_id="NOT_CONFIGURED_IN_ADAPTER", # Deixa claro que este ID veio do adapter
            secret="NOT_CONFIGURED_IN_ADAPTER"
        )
