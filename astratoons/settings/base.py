# astratoons/settings/base.py

import os
from pathlib import Path
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

# --- Caminhos do Projeto ---------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR / 'astratoons'


# --- Aplicações Instaladas ------------------------------------------------
INSTALLED_APPS = [
    # Django Core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Wagtail CMS
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail',
    'wagtail.contrib.settings',
    'modelcluster',
    'taggit',
    'wagtail_modeladmin',

    # Ferramentas e bibliotecas de terceiros
    'crispy_forms',
    'crispy_bootstrap5',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.discord',
    'avatar',
    'rest_framework',
    'knox',
    'paypal.standard.ipn',

    # Nossas Aplicações
    'core',
    'home',
    'search',
    'accounts',
    'manga',
    'novels',
    'solo',
    'subscriptions',
    'comments',
]


# --- Middleware ------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
]


# --- Configurações Principais do Django -----------------------------------
ROOT_URLCONF = 'astratoons.urls'
WSGI_APPLICATION = 'astratoons.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SITE_ID = 1

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [ BASE_DIR / 'templates', ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'wagtail.contrib.settings.context_processors.settings',
                'comments.context_processors.notifications',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': { 'timeout': 20, },
    }
}


# --- Segurança e Autenticação ---------------------------------------------
AUTH_PASSWORD_VALIDATORS = [ {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}, ]
AUTHENTICATION_BACKENDS = [ 'django.contrib.auth.backends.ModelBackend', 'allauth.account.auth_backends.AuthenticationBackend', ]
CSRF_TRUSTED_ORIGINS = [
    'https://9770-131-196-144-132.ngrok-free.app',
    'http://localhost:8000',
    'http://127.0.0.1:8000'
]


# --- Internacionalização (I18N) -------------------------------------------
LANGUAGE_CODE = 'pt-br'
LANGUAGES = [ ('pt-br', _('Português')), ('en', _('English')), ('fr', _('Français')), ('es', _('Español')), ]
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [ os.path.join(BASE_DIR, 'locale'), ]


# --- Arquivos Estáticos e de Mídia -----------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / 'static', ]
STATIC_ROOT = BASE_DIR / 'static_collected'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = { "default": { "BACKEND": "django.core.files.storage.FileSystemStorage", }, "staticfiles": { "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage", }, }


# --- Configurações do Wagtail ----------------------------------------------
WAGTAIL_SITE_NAME = 'AstraToons'
# ATENÇÃO: A linha abaixo é ideal para desenvolvimento. Em produção,
# você deve sobrescrever esta variável no seu settings/production.py
# com o seu domínio real (ex: 'https://astratoons.com')
WAGTAILADMIN_BASE_URL = 'http://localhost:8000'
WAGTAILSEARCH_BACKENDS = { 'default': { 'BACKEND': 'wagtail.search.backends.database', } }
WAGTAILDOCS_EXTENSIONS = ['mp3','m4a', 'ogg', 'wav','csv', 'docx', 'key', 'odt', 'pdf', 'pptx', 'rtf', 'txt', 'xlsx', 'zip']


# --- Configurações do `django-crispy-forms` --------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- Configurações do `django-rest-framework` e `knox` --------------------
REST_FRAMEWORK = { 'DEFAULT_AUTHENTICATION_CLASSES': ['knox.auth.TokenAuthentication',], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated',] }


# --- Configurações do `django-allauth` (Autenticação de Usuários) ---------
LOGIN_REDIRECT_URL = reverse_lazy('accounts:profile')
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = 'account_login'

# --- AVISO CORRIGIDO ---
# Esta é a configuração correta e moderna para um sistema que usa apenas
# email para login e cadastro, sem um campo de 'username'.
# Isso resolve os avisos de conflito e de métodos obsoletos.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'none' # Mude para 'mandatory' em produção se desejar.

# Configurações Adicionais
ACCOUNT_SESSION_REMEMBER = True
LOGOUT_ON_GET = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_FORMS = { 'signup': 'accounts.forms.CustomUserCreationForm', }
ACCOUNT_ADAPTER = 'allauth.account.adapter.DefaultAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_PROVIDERS = { 'google': { 'SCOPE': ['profile', 'email'], 'AUTH_PARAMS': {'access_type': 'online', 'prompt': 'select_account'}, }, 'discord': { 'SCOPE': ['identify', 'email'], } }
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # Para ver emails no terminal


# --- Configurações do `django-avatar` -------------------------------------
AVATAR_GRAVATAR_BACKUP = True
AVATAR_GRAVATAR_DEFAULT = 'identicon'
AVATAR_STORAGE_DIR = 'avatars'
AVATAR_CLEANUP_DELETED = True


# --- Configurações do PayPal ---
PAYPAL_TEST = True  # Para usar o ambiente Sandbox. Mude para False em produção.
PAYPAL_RECEIVER_EMAIL = 'sb-owrom44606592@business.example.com'  # SUBSTITUA PELO SEU EMAIL DE VENDEDOR DO SANDBOX
