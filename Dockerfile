# ---- Estágio 1: Builder ----
FROM python:3.12-bookworm as builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gettext libpq-dev libmariadb-dev libjpeg62-turbo-dev zlib1g-dev libwebp-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir "gunicorn==23.0.0"
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ---- Estágio 2: Final ----
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends gettext && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash wagtail
ENV PYTHONUNBUFFERED=1 PORT=8000 DJANGO_SETTINGS_MODULE=astratoons.settings.production DJANGO_WSGI_MODULE=astratoons.wsgi

# Diretório onde o código e o banco de dados ficarão
WORKDIR /home/wagtail/web

# Copia as dependências primeiro
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir "gunicorn==23.0.0"
RUN pip install --no-cache /wheels/*

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# Muda o dono de tudo para o usuário 'wagtail' ANTES de rodar os comandos
RUN chown -R wagtail:wagtail /home/wagtail/web

# Muda para o usuário não-root
USER wagtail

# Executa comandos de preparação como o usuário 'wagtail'
# Django vai criar o db.sqlite3 aqui com as permissões corretas
RUN python manage.py migrate --noinput
RUN python manage.py compilemessages
RUN python manage.py collectstatic --noinput --clear

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "astratoons.wsgi:application"]