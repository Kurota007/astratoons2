import re
import markdown
from pypdf import PdfReader

def parse_text_to_chapters(full_text_content):
    """
    Recebe um texto único e o divide em capítulos.
    Retorna uma lista de dicionários, onde cada dicionário é um capítulo.
    """
    chapters_data = []
    chapter_title_pattern = re.compile(
        r"^\s*Cap[íi]tulo\s+(?P<number>[\w\s().-]+?)\s*(?:[:–—]\s*(?P<name>.+))?$",
        re.IGNORECASE | re.MULTILINE
    )
    title_matches = list(chapter_title_pattern.finditer(full_text_content))

    for i, current_match in enumerate(title_matches):
        chapter_number_str = current_match.group('number').strip()
        chapter_optional_name_str = current_match.group('name').strip() if current_match.group('name') else ""

        full_title = f"Capítulo {chapter_number_str}"
        if chapter_optional_name_str:
            full_title += f": {chapter_optional_name_str}"

        content_start_pos = current_match.end()
        content_end_pos = title_matches[i+1].start() if (i + 1) < len(title_matches) else len(full_text_content)
        raw_chapter_content = full_text_content[content_start_pos:content_end_pos].strip()

        content_start_chunk = "\n".join(raw_chapter_content.lstrip().splitlines()[:5]).lower()
        if ("tradutor:" in content_start_chunk or "editor:" in content_start_chunk) and raw_chapter_content:
            html_content = markdown.markdown(raw_chapter_content, extensions=['extra', 'nl2br', 'fenced_code'])
            
            chapters_data.append({
                'title': full_title,
                'content': html_content
            })
            
    return chapters_data


def extract_chapters_from_pdf(pdf_file_object):
    """
    Recebe um objeto de arquivo PDF da memória, extrai o texto
    e retorna uma lista de dicionários de capítulos.
    """
    try:
        full_extracted_text = ""
        reader = PdfReader(pdf_file_object)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                full_extracted_text += page_text + "\n\n"
        
        if not full_extracted_text.strip():
            return []

        chapters = parse_text_to_chapters(full_extracted_text)
        return chapters

    except Exception as e:
        print(f"Ocorreu um erro ao processar o PDF: {e}")
        return None