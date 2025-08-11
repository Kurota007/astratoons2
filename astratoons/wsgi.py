# astratoons/wsgi.py

import os
from django.core.wsgi import get_wsgi_application

# Verifica se a variável de ambiente DJANGO_SETTINGS_MODULE está definida,
# senão, define como padrão o seu arquivo de settings (ajuste se necessário)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'astratoons.settings.dev')

# Cria o objeto 'application' que o servidor WSGI vai usar
application = get_wsgi_application()