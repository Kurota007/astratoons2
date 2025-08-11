# novels/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _

class SingleChapterForm(forms.Form):
    chapter_identifier = forms.CharField(
        label=_("Número/Identificador do Capítulo"),
        help_text=_("Ex: '1', '10.5', 'Prólogo', 'Volume 2 Capítulo 5'. Obrigatório."),
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'input'})
    )
    chapter_name_optional = forms.CharField(
        label=_("Nome do Capítulo (Opcional)"),
        help_text=_("Um título descritivo para o capítulo, se houver."),
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'input'})
    )
    markdown_content = forms.CharField(
        label=_("Conteúdo do Capítulo"),
        widget=forms.Textarea(attrs={'class': 'input', 'rows': 15, 'id': 'markdown-editor'}),
        help_text=_("Use Markdown para formatação. Ex: **negrito**, *itálico*, # Cabeçalho, - Lista. A prévia HTML aparecerá abaixo.")
    )
    main_content_html = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    def clean_chapter_identifier(self):
        data = self.cleaned_data.get('chapter_identifier')
        if not data or not data.strip():
            raise forms.ValidationError(_("Este campo é obrigatório."))
        return data

    def clean_markdown_content(self):
        data = self.cleaned_data.get('markdown_content')
        if not data or not data.strip():
            raise forms.ValidationError(_("O conteúdo do capítulo (Markdown) não pode estar vazio."))
        return data

class ZipUploadForm(forms.Form):
    zip_file = forms.FileField(
        label=_("Arquivo .ZIP com Capítulos"),
        help_text=_("Envie um arquivo .zip contendo arquivos .txt (um por capítulo) ou PDFs (com múltiplos capítulos). Nomes de arquivo podem ser usados para inferir números/títulos de capítulo."),
    )

class PDFUploadForm(forms.Form):
    pass