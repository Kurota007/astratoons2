# manga/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import zipfile
import logging

# Importe os modelos necessários
from .models import MangaPage, MangaComment # Certifique-se que MangaComment está importado

logger = logging.getLogger(__name__)

class CombinedUploadForm(forms.Form):
    """Formulário para selecionar Manga e fazer upload do ZIP na mesma tela."""
    manga_selection = forms.ModelChoiceField(
        queryset=MangaPage.objects.live().order_by('title'), 
        label=_("Obra (Série de Mangá)"),
        empty_label=_("--- Selecione a Obra ---"),
        required=True,
        help_text=_("Selecione a obra para a qual este upload se destina.")
    )
    zip_file = forms.FileField(
        label=_("Arquivo ZIP do(s) Capítulo(s)"),
        required=True,
        help_text=_(
            "ZIP com pastas numeradas (ex: '01', '10.5') contendo imagens."
        )
    )

    def clean_zip_file(self):
        zip_file = self.cleaned_data.get('zip_file')
        if not zip_file:
            return zip_file
        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                if not zf.namelist(): 
                    raise ValidationError(_("O arquivo ZIP enviado está vazio."))
        except zipfile.BadZipFile:
            raise ValidationError(_("Arquivo inválido. Por favor, envie um arquivo ZIP válido."))
        except Exception as e:
            logger.error(f"Erro inesperado ao validar o arquivo ZIP: {e}", exc_info=True)
            raise ValidationError(_("Ocorreu um erro ao tentar ler o arquivo ZIP: %(error)s") % {'error': e})
        
        if hasattr(zip_file, 'seek') and callable(zip_file.seek):
            zip_file.seek(0)
        return zip_file

# --- Formulário para Comentários ---
class MangaCommentForm(forms.ModelForm): 
    class Meta:
        model = MangaComment
        fields = ['text'] 
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': _('Escreva seu comentário aqui...'), 
                'class': 'input comment-textarea', 
                'aria-label': _('Campo de comentário') 
            }),
        }
        labels = {
            'text': '', 
        }
        help_texts = {
            'text': None, 
        }