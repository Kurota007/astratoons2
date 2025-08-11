# novels/chapter_processing.py

import re
import markdown

def replace_custom_image_tags_in_html(html_content):
    return html_content

def parse_pdf_text_into_chapters(full_text_content):
    chapters_data = []
    
    chapter_title_pattern = re.compile(
        r"^\s*Cap[íi]tulo\s+(?P<number>[\w\s().-]+?)\s*(?:[:–—]\s*(?P<name>.+))?$",
        re.IGNORECASE | re.MULTILINE
    )

    title_matches = list(chapter_title_pattern.finditer(full_text_content))

    if not title_matches:
        if full_text_content.strip():
            content_start_chunk = "\n".join(full_text_content.lstrip().splitlines()[:5]).lower()
            if "tradutor:" in content_start_chunk or "editor:" in content_start_chunk:
                html_content = markdown.markdown(full_text_content, extensions=['extra', 'nl2br', 'fenced_code'])
                final_html_content = replace_custom_image_tags_in_html(html_content)
                chapters_data.append({
                    'identifier': '1',
                    'name_optional': 'Texto Completo do PDF',
                    'html_content': final_html_content,
                })
        return chapters_data

    for i, current_match in enumerate(title_matches):
        chapter_number_str = current_match.group('number').strip()
        chapter_optional_name_str = current_match.group('name').strip() if current_match.group('name') else ""
        
        if chapter_optional_name_str:
            cleaned_name = chapter_optional_name_str.replace('-', ' ').replace('_', ' ')
            chapter_optional_name_str = ' '.join(cleaned_name.split()).capitalize()
        
        content_start_pos = current_match.end()
        content_end_pos = len(full_text_content) if (i + 1) >= len(title_matches) else title_matches[i+1].start()
        raw_chapter_content = full_text_content[content_start_pos:content_end_pos].strip()

        if not raw_chapter_content:
            continue

        content_start_chunk = "\n".join(raw_chapter_content.lstrip().splitlines()[:5]).lower()
        if "tradutor:" in content_start_chunk or "editor:" in content_start_chunk:
            html_content = markdown.markdown(raw_chapter_content, extensions=['extra', 'nl2br', 'fenced_code'])
            final_html_content = replace_custom_image_tags_in_html(html_content)

            chapters_data.append({
                'identifier': chapter_number_str,
                'name_optional': chapter_optional_name_str,
                'html_content': final_html_content,
            })
            
    return chapters_data