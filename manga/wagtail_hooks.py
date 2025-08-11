# manga/wagtail_hooks.py
import logging
from django.urls import path, include, reverse
from django.utils.translation import gettext_lazy as _

from wagtail import hooks
from wagtail.admin.menu import MenuItem

from manga import admin_urls as manga_admin_urls

logger = logging.getLogger(__name__)

@hooks.register('register_admin_urls')
def register_manga_upload_urls():
    return [
        path('manga-uploader/', include((manga_admin_urls, 'manga_upload_admin'))),
    ]

@hooks.register('register_admin_menu_item')
def register_manga_upload_menu_item():
    try:
        upload_url = reverse('manga_upload_admin:upload_options')
        
        return MenuItem(
            label=_('Upar Mangás'),
            url=upload_url,
            icon_name='doc-full-inverse', 
            order=260
        )
    except Exception as e:
        logger.error(f"Erro ao criar MenuItem 'Upar Mangás': {e}", exc_info=True)
        return None