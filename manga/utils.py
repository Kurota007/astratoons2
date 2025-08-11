import zipfile
import os
import logging
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from PIL import Image as PillowImage

try:
    import pillow_avif
except ImportError:
    pillow_avif = None

from .models import MangaPage, MangaChapterPage, ChapterImage

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

@transaction.atomic
def process_manga_zip(manga_page: MangaPage, zip_file_obj, owner_user):
    processing_messages_list = []
    chapters_processed_count = 0
    
    zip_file_obj.seek(0)

    try:
        with zipfile.ZipFile(zip_file_obj, 'r') as zip_fp:
            chapter_files_map = {}
            all_files_info = sorted(zip_fp.infolist(), key=lambda x: x.filename)

            for item in all_files_info:
                if item.is_dir() or item.filename.startswith('__MACOSX/') or '/.' in item.filename:
                    continue
                try:
                    file_path_in_zip = Path(item.filename)
                    if not file_path_in_zip.parent or str(file_path_in_zip.parent) == '.':
                        continue
                    chapter_folder_name = file_path_in_zip.parent.name
                    if Path(item.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                        continue
                except IndexError:
                    continue

                if chapter_folder_name not in chapter_files_map:
                    chapter_files_map[chapter_folder_name] = []
                chapter_files_map[chapter_folder_name].append(item)

            if not chapter_files_map:
                msg_err = _("Nenhuma pasta de capítulo válida ou arquivos de imagem permitidos encontrados no ZIP.")
                processing_messages_list.append((messages.ERROR, msg_err))
                return False, processing_messages_list

            for chapter_folder_name, image_items in chapter_files_map.items():
                try:
                    num_str_for_db = str(float(chapter_folder_name))
                    if num_str_for_db.endswith('.0'): num_str_for_db = num_str_for_db[:-2]
                except (ValueError, TypeError):
                    num_str_for_db = chapter_folder_name

                actual_chapter_page_slug = slugify(str(num_str_for_db).replace('.', '-'))
                chapter_final_title = f"{manga_page.title} - Capítulo {num_str_for_db}"

                try:
                    chapter_page = MangaChapterPage.objects.child_of(manga_page).get(slug=actual_chapter_page_slug)
                    chapter_page.chapter_images.all().delete()
                    processing_messages_list.append((messages.INFO, _("Atualizando capítulo '%(title)s'. Imagens antigas removidas.") % {'title': chapter_page.title}))
                except MangaChapterPage.DoesNotExist:
                    chapter_page = MangaChapterPage(
                        title=chapter_final_title,
                        chapter_number=num_str_for_db,
                        owner=owner_user,
                        live=True,
                        release_date=timezone.now(),
                    )
                    manga_page.add_child(instance=chapter_page)
                    chapter_page.save_revision(user=owner_user).publish()
                    processing_messages_list.append((messages.SUCCESS, _("Capítulo '%(title)s' criado com sucesso.") % {'title': chapter_page.title}))
                    chapters_processed_count += 1
                
                images_to_create = []
                final_image_index = 0
                slice_height = getattr(settings, 'ALTURA_FATIA', 1600)
                save_params = {'format': 'AVIF', 'quality': 55, 'subsampling': '4:2:0', 'speed': 7}
                
                sorted_image_items = sorted(image_items, key=lambda x: x.filename)
                
                for image_info in sorted_image_items:
                    original_filename = os.path.basename(image_info.filename)
                    
                    try:
                        image_data = zip_fp.read(image_info.filename)
                        img = PillowImage.open(BytesIO(image_data))
                        width, height = img.size
                        
                        if height > slice_height:
                            for y in range(0, height, slice_height):
                                box = (0, y, width, min(y + slice_height, height))
                                slice_img = img.crop(box).convert("RGB")
                                
                                buffer = BytesIO()
                                slice_img.save(buffer, **save_params)
                                
                                avif_filename = f"{final_image_index:03d}.avif"
                                
                                images_to_create.append(ChapterImage(
                                    page=chapter_page,
                                    encrypted_file=ContentFile(buffer.getvalue(), name=avif_filename),
                                    original_filename=f"{original_filename} (fatia {final_image_index})",
                                    sort_order=final_image_index
                                ))
                                final_image_index += 1
                        else:
                            buffer = BytesIO()
                            img.convert("RGB").save(buffer, **save_params)
                            
                            original_stem = Path(original_filename).stem
                            avif_filename = f"{final_image_index:03d}_{original_stem}.avif"

                            images_to_create.append(ChapterImage(
                                page=chapter_page,
                                encrypted_file=ContentFile(buffer.getvalue(), name=avif_filename),
                                original_filename=original_filename,
                                sort_order=final_image_index
                            ))
                            final_image_index += 1

                    except Exception as e:
                        logger.error(f"Erro ao processar a imagem {original_filename} do ZIP: {e}")
                        continue

                if images_to_create:
                    ChapterImage.objects.bulk_create(images_to_create)
                    msg_bulk_ok = _("%(count)d fatias de imagem foram salvas para o capítulo '%(title)s'.") % {'count': len(images_to_create), 'title': chapter_page.title}
                    processing_messages_list.append((messages.INFO, msg_bulk_ok))

        return True, processing_messages_list

    except zipfile.BadZipFile:
        msg = _("ERRO FATAL: O arquivo enviado não é um ZIP válido ou está corrompido.")
        processing_messages_list.append((messages.ERROR, msg))
        return False, processing_messages_list
    except Exception as e:
        logger.error(f"UTILS: Exceção inesperada no processamento do ZIP: {e}", exc_info=True)
        msg = _("ERRO FATAL INESPERADO: %(error)s") % {'error': str(e)}
        processing_messages_list.append((messages.ERROR, msg))
        return False, processing_messages_list