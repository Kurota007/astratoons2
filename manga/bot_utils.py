# /home/stalker/astratoons/manga/bot_utils.py

import requests
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_role_update_to_bot(user_discord_id: str, role_id: str, action: str):
    bot_api_base_url = getattr(settings, 'DISCORD_BOT_API_BASE_URL', None)
    django_to_bot_api_key = getattr(settings, 'DJANGO_TO_BOT_API_KEY', None)

    if not bot_api_base_url or not django_to_bot_api_key:
        logger.error("bot_utils: DISCORD_BOT_API_BASE_URL ou DJANGO_TO_BOT_API_KEY não definidos nos settings.")
        return False, "Configuração do bot ausente no Django."

    endpoint_url = f"{bot_api_base_url.rstrip('/')}/update-role"

    payload = {
        "user_discord_id": str(user_discord_id),
        "role_id": str(role_id),
        "action": action
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {django_to_bot_api_key}"
    }

    logger.info(f"Enviando requisição de cargo para o Bot: URL='{endpoint_url}', Payload={payload}")

    try:
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        response_data = response.json()
        if response_data.get('status') == 'success':
            logger.info(f"Sucesso na API do Bot (role): {response_data.get('message')}")
            return True, response_data
        else:
            error_message = response_data.get('message', "Erro não especificado pelo Bot.")
            logger.warning(f"Erro reportado pela API do Bot (role): {error_message}")
            return False, error_message

    except requests.exceptions.RequestException as e:
        logger.exception(f"Falha na requisição para o bot (role) em {endpoint_url}: {e}")
        return False, f"Erro de comunicação com o bot: {e}"