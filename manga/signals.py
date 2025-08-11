import os
import requests
import json
import logging
import math
import datetime
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from wagtail.signals import page_published
from wagtail.models import Site

from allauth.socialaccount.models import SocialAccount

from .models import (
    GlobalSettings, MangaChapterPage, MangaPage, Favorite, ChapterImage
)

from .bot_utils import send_role_update_to_bot

logger = logging.getLogger(__name__)

@receiver(post_delete, sender=ChapterImage)
def delete_page_image_on_delete(sender, instance, **kwargs):
    """
    Deleta o arquivo de imagem criptografada de uma ChapterImage
    quando o objeto é deletado do banco de dados.
    """
    if instance.encrypted_file:
        if hasattr(instance.encrypted_file, 'path') and os.path.isfile(instance.encrypted_file.path):
            try:
                os.remove(instance.encrypted_file.path)
                logger.info(f"Arquivo de página deletado do disco: {instance.encrypted_file.path}")
            except OSError as e:
                logger.error(f"Erro ao deletar arquivo de página {instance.encrypted_file.path}: {e}")

@receiver(post_delete, sender=MangaChapterPage)
def delete_chapter_assets_on_delete(sender, instance, **kwargs):
    """
    1. Deleta a imagem de thumbnail do capítulo.
    2. Deleta a pasta de imagens do capítulo.
    3. Deleta a pasta da thumbnail do capítulo (se vazia).
    """
    if hasattr(instance.get_parent(), 'specific'):
        manga_page = instance.get_parent().specific
        manga_slug = manga_page.slug
        chapter_number_raw = str(instance.chapter_number)
        
        safe_chapter_folder_name = ''.join(c if c.isalnum() or c in '.-_' else '_' for c in chapter_number_raw).strip('_')
        if not safe_chapter_folder_name:
            safe_chapter_folder_name = 'cap_extra'

        pages_directory = os.path.join(settings.MEDIA_ROOT, 'encrypted_manga_slices', manga_slug, safe_chapter_folder_name)
        
        try:
            if os.path.isdir(pages_directory):
                for filename in os.listdir(pages_directory):
                    file_path = os.path.join(pages_directory, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(pages_directory)
                logger.info(f"Pasta de páginas do capítulo deletada com sucesso: {pages_directory}")
        except OSError as e:
            logger.error(f"Erro ao tentar deletar a pasta de páginas do capítulo {pages_directory}: {e}")

    if hasattr(instance, 'thumbnail') and instance.thumbnail:
        thumbnail_path = instance.thumbnail.path
        thumb_directory = os.path.dirname(thumbnail_path)
        
        if os.path.isfile(thumbnail_path):
            try:
                os.remove(thumbnail_path)
                logger.info(f"Arquivo de thumbnail deletado do disco: {thumbnail_path}")
            except OSError as e:
                logger.error(f"Erro ao deletar arquivo de thumbnail {thumbnail_path}: {e}")

        try:
            if os.path.isdir(thumb_directory) and not os.listdir(thumb_directory):
                os.rmdir(thumb_directory)
                logger.info(f"Pasta de thumbnail do capítulo deletada: {thumb_directory}")
        except OSError as e:
            logger.error(f"Erro ao tentar deletar a pasta de thumbnail {thumb_directory}: {e}")

@receiver(post_delete, sender=MangaPage)
def delete_manga_cover_on_delete(sender, instance, **kwargs):
    """
    Registra a deleção da capa da obra. A deleção física é gerenciada pelo Wagtail.
    """
    if instance.cover:
        try:
            file_path = instance.cover.file.path
            logger.info(f"Objeto de capa da obra '{instance.title}' (arquivo: {file_path}) deletado do banco. A deleção física é gerenciada pelo Wagtail.")
        except Exception as e:
            logger.error(f"Erro ao acessar o caminho do arquivo de capa da obra para deleção: {e}")

@receiver(page_published, sender=MangaChapterPage)
def on_chapter_publish(sender, instance, **kwargs):
    """
    Função principal que é acionada quando um capítulo é publicado.
    Ela dispara as ações de limpeza de cache e notificação do Discord.
    """
    logger.info(f"Sinal 'page_published' acionado para o capítulo: '{instance.title}' (ID: {instance.id})")
    
    purge_cloudflare_cache(instance)
    notify_discord(instance)

def purge_cloudflare_cache(instance):
    """Lógica de limpeza do cache do Cloudflare."""
    logger.info("Cloudflare: Tentando limpar o cache...")
    try:
        current_site = instance.get_site() or Site.objects.get(is_default_site=True)
        settings_obj = GlobalSettings.for_site(current_site)
        zone_id = getattr(settings_obj, 'cloudflare_zone_id', None)
        api_token = getattr(settings_obj, 'cloudflare_api_token', None)

        if not zone_id or not api_token:
            logger.warning("Cloudflare: Credenciais não configuradas no painel. Pulando limpeza.")
            return

        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        data = {"purge_everything": True}
        api_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"

        response = requests.post(api_url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("success"):
            logger.info("✅ Cloudflare: Cache limpo com sucesso!")
        else:
            logger.error(f"❌ Cloudflare: API retornou um erro: {result.get('errors')}")

    except Exception as e:
        logger.error(f"❌ Cloudflare: Ocorreu um erro inesperado ao tentar limpar o cache. Erro: {e}")


def notify_discord(instance):
    """Lógica de notificação para o bot do Discord com o novo layout."""
    logger.info("Discord: Tentando notificar...")
    bot_api_base_url = getattr(settings, 'DISCORD_BOT_API_BASE_URL', None)
    django_to_bot_api_key = getattr(settings, 'DJANGO_TO_BOT_API_KEY', None)

    if not bot_api_base_url or not django_to_bot_api_key:
        logger.error("Discord: Credenciais da API do Bot não definidas.")
        return

    endpoint_url = f"{bot_api_base_url.rstrip('/')}/announce-chapter"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {django_to_bot_api_key}"}

    try:
        manga_page = instance.get_parent().specific
        base_url = "https://astratoons.com"

        genres_str = ""
        if hasattr(manga_page, 'genre'):
            genres_manager = manga_page.genre
            if genres_manager:
                genres_list = [tag.name for tag in genres_manager.all()]
                genres_str = ", ".join(genres_list)

        chapter_cover_url = None
        if instance.thumbnail and hasattr(instance.thumbnail, 'url'):
            chapter_cover_url = base_url + instance.thumbnail.url
        
        series_thumbnail_url = None
        series_role_id = str(manga_page.discord_series_role_id) if manga_page.discord_series_role_id else None
        custom_path = f"/manga/{manga_page.slug}/capitulo/{instance.slug}/"
        final_chapter_url = base_url + custom_path
        
        payload = {
            "series_title": manga_page.title,
            "series_genres": genres_str,
            "series_thumbnail_url": series_thumbnail_url,
            "cover_image_url": chapter_cover_url,
            "chapter_number": str(instance.chapter_number),
            "chapter_url": final_chapter_url,
            "series_role_id": series_role_id
        }

    except Exception as e:
        logger.exception(f"Discord: Erro ao montar o payload para '{instance.title}': {e}")
        return

    logger.info(f"Discord: Enviando notificação. Payload={json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        logger.info(f"✅ Discord: Notificação enviada com sucesso! Resposta: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.exception(f"❌ Discord: Falha ao enviar notificação para o bot: {e}")


@receiver(post_save, sender=Favorite)
def handle_favorite_added(sender, instance, created, **kwargs):
    if created:
        try:
            user = instance.user
            manga_page = instance.manga
            if manga_page.discord_series_role_id:
                social_account = SocialAccount.objects.get(user=user, provider='discord')
                send_role_update_to_bot(social_account.uid, manga_page.discord_series_role_id, "add")
        except SocialAccount.DoesNotExist:
            logger.info(f"Usuário {instance.user.username} favoritou, mas não tem Discord conectado.")
        except Exception as e:
            logger.exception(f"Erro no sinal handle_favorite_added: {e}")


@receiver(post_delete, sender=Favorite)
def handle_favorite_removed(sender, instance, **kwargs):
    try:
        user = instance.user
        manga_page = instance.manga
        if manga_page.discord_series_role_id:
            social_account = SocialAccount.objects.get(user=user, provider='discord')
            send_role_update_to_bot(social_account.uid, manga_page.discord_series_role_id, "remove")
    except SocialAccount.DoesNotExist:
        logger.info(f"Usuário {instance.user.username} desfavoritou, mas não tem Discord conectado.")
    except Exception as e:
        logger.exception(f"Erro no sinal handle_favorite_removed: {e}")


# ===================================================================
#           LÓGICA FINAL DE NOTIFICAÇÃO DE METAS DE DOAÇÃO
# ===================================================================

def send_discord_donation_notification(manga, total_goals_achieved, new_goals_met):
    """
    Envia uma notificação embed para o Discord da staff, informando quantos
    novos "capítulos" foram comprados de uma só vez.
    """
    webhook_url = getattr(settings, 'DISCORD_STAFF_WEBHOOK_URL', None)
    if not webhook_url:
        logger.warning("AVISO: A 'DISCORD_STAFF_WEBHOOK_URL' não está configurada. Notificação de meta para a staff não enviada.")
        return

    try:
        current_site = manga.get_site() or Site.objects.get(is_default_site=True)
        base_url = current_site.root_url
    except Exception:
        base_url = "https://astratoons.com"

    manga_url = base_url + manga.get_url()
    cover_url = ""
    if manga.cover and hasattr(manga.cover, 'url'):
        cover_url = base_url + manga.cover.url

    if new_goals_met == 1:
        title = "🎯 1 Novo Capítulo Comprado!"
        description = f"A meta de doação para **{manga.title}** foi atingida!"
    else:
        title = f"🎯 {new_goals_met} Novos Capítulos Comprados!"
        description = f"**{new_goals_met} metas** de doação para **{manga.title}** foram atingidas de uma vez!"

    total_donated_for_goals = total_goals_achieved * manga.donation_goal

    payload = {
        "username": "Astratoons Bot",
        "avatar_url": "https://astratoons.com/media/images/ChatGPT_Image_16_de_mai._de_2025_17_47_46.width-180.png",
        "embeds": [
            {
                "title": title,
                "url": manga_url,
                "color": 3447003,
                "description": description,
                "fields": [
                    {"name": "Total Arrecadado na Obra", "value": f"🪙 {manga.current_donations}", "inline": True},
                    {"name": "Valor das Metas Atingidas", "value": f"🪙 {total_donated_for_goals}", "inline": True},
                ],
                "thumbnail": {
                    "url": cover_url
                },
                "footer": {
                    "text": f"Notificação para a Staff | {manga.title}"
                },
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Notificação de {new_goals_met} meta(s) para '{manga.title}' enviada com sucesso para a staff.")
    except requests.exceptions.RequestException as e:
        logger.error(f"ERRO: Falha ao enviar notificação de meta via webhook para '{manga.title}'. Erro: {e}")

@receiver(post_save, sender=MangaPage)
def check_donation_goal_met(sender, instance, **kwargs):
    """
    Verifica se um novo múltiplo da meta de doação foi atingido.
    Ex: Meta = 400. Notifica em 400, 800, 1200, etc.
    A staff deve ajustar os valores manualmente no admin se desejar.
    """
    manga = instance
    goal = manga.donation_goal
    
    if not goal or goal <= 0:
        return

    donations = manga.current_donations
    sent_count = manga.donation_notifications_sent
    
    total_goals_achieved = math.floor(donations / goal)

    if total_goals_achieved > sent_count:
        new_goals_met = total_goals_achieved - sent_count
        
        send_discord_donation_notification(manga, total_goals_achieved, new_goals_met)
        
        post_save.disconnect(check_donation_goal_met, sender=MangaPage)
        
        try:
            instance.donation_notifications_sent = total_goals_achieved
            instance.save(update_fields=['donation_notifications_sent'])
        finally:
            post_save.connect(check_donation_goal_met, sender=MangaPage)