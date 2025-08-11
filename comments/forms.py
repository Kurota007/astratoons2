# comments/forms.py

from django import forms
from .models import Comment

class CommentForm(forms.ModelForm):
    # Campos extras que não existem no modelo, mas que usaremos no template
    # para controlar a formatação do texto.
    use_bold = forms.BooleanField(required=False, label="Negrito")
    use_italic = forms.BooleanField(required=False, label="Itálico")

    class Meta:
        model = Comment
        # --- CORREÇÃO PRINCIPAL AQUI ---
        # A lista de 'fields' agora corresponde exatamente aos nomes dos campos
        # que definimos no seu arquivo models.py.
        fields = ('content', 'image', 'is_spoiler', 'image_is_spoiler',)

        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Escreva seu comentário...',
                'rows': 4,
            }),
            # Usamos um widget de arquivo padrão.
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            # Checkboxes para os campos de spoiler.
            'is_spoiler': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image_is_spoiler': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
        # Labels amigáveis para serem usados no template
        labels = {
            'content': '',
            'image': 'Enviar Imagem',
            'is_spoiler': 'Marcar texto como spoiler',
            'image_is_spoiler': 'Marcar imagem como spoiler',
        }
    
    def clean(self):
        """
        Validação customizada para garantir que o usuário enviou
        ou um texto, ou uma imagem, mas não ambos vazios.
        """
        cleaned_data = super().clean()
        content = cleaned_data.get("content")
        image = cleaned_data.get("image")

        if not content and not image:
            raise forms.ValidationError(
                "Você precisa escrever um comentário ou enviar uma imagem.",
                code='required'
            )
        
        return cleaned_data