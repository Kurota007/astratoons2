from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-y%w7vj@_2=8xnf-#q=nn!gew#ozf!r8o67=3g)coe+nymtk6ws"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =========================================================================
# === INÍCIO DA CORREÇÃO ===
# =========================================================================
# Garante que o Django use o backend de autenticação padrão junto com o allauth
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)
# =========================================================================
# === FIM DA CORREÇÃO ===
# =========================================================================


try:
    from .local import *
except ImportError:
    pass