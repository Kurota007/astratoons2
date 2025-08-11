from django import forms
from django.contrib.auth import get_user_model
from allauth.account.forms import SignupForm
from django.utils.translation import gettext_lazy as _
from .models import Profile, UserBadge, CosmeticBadge

User = get_user_model()


class ManualLoginForm(forms.Form):
    login = forms.CharField(label="Usuário ou E-mail", max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, label="Senha")


ref_input_classes = 'w-full bg-gray-800 border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-600 focus:border-transparent'
ref_input_readonly_classes = 'w-full bg-gray-700 border border-gray-600 rounded-md py-2 px-3 text-gray-300 cursor-not-allowed'
ref_textarea_classes = ref_input_classes
ref_select_classes = 'appearance-none w-full bg-gray-800 border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-600 focus:border-transparent'


class UserProfileEditForm(forms.ModelForm):
    username = forms.CharField(
        label=_("Nome de usuário"),
        widget=forms.TextInput(attrs={'class': ref_input_readonly_classes, 'readonly': True}),
        disabled=True,
        required=False
    )
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={'class': ref_input_readonly_classes, 'readonly': True}),
        disabled=True,
        required=False
    )
    first_name = forms.CharField(
        required=False,
        label=_("Nome"),
        widget=forms.TextInput(attrs={'class': ref_input_classes, 'placeholder': _('Seu nome')})
    )
    last_name = forms.CharField(
        required=False,
        label=_("Sobrenome"),
        widget=forms.TextInput(attrs={'class': ref_input_classes, 'placeholder': _('Seu sobrenome')})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']


class ProfileInfoForm(forms.ModelForm):
    display_name = forms.CharField(
        required=False,
        label=_("Nome de Exibição"),
        widget=forms.TextInput(attrs={
            'class': ref_input_classes,
            'placeholder': _('Como você quer ser chamado')
        })
    )
    
    bio = forms.CharField(
        required=False,
        label=_("Sobre você"),
        widget=forms.Textarea(attrs={
            'class': ref_textarea_classes,
            'rows': 4,
            'maxlength': 200,
            'placeholder': _('Conte um pouco sobre você...')
        }),
    )

    active_badges = forms.ModelMultipleChoiceField(
        queryset=CosmeticBadge.objects.none(),
        required=False,
        label=_("Badges Ativos"),
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Profile
        fields = ['display_name', 'bio', 'active_badges']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            owned_badge_ids = UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
            self.fields['active_badges'].queryset = CosmeticBadge.objects.filter(id__in=owned_badge_ids)
    
    def clean_active_badges(self):
        badges = self.cleaned_data.get('active_badges')
        if badges and len(badges) > 2:
            raise forms.ValidationError(_("Você pode selecionar no máximo 2 badges para exibir."))
        return badges


class ProfileSiteAvatarForm(forms.ModelForm):
    site_avatar = forms.ImageField(
        required=False,
        label="",
        widget=forms.FileInput(attrs={
            'class': 'file-input',
            'accept': 'image/jpeg,image/png,image/gif,image/webp',
            'id': 'id_site_avatar_input'
        })
    )
    class Meta:
        model = Profile
        fields = ['site_avatar']


class CustomUserCreationForm(SignupForm):
    first_name = forms.CharField(
        label=_("Primeiro nome"),
        max_length=150,
        required=False,
    )
    last_name = forms.CharField(
        label=_("Sobrenome"),
        max_length=150,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"] = forms.CharField(
            label=_("Nome de usuário"),
            max_length=150,
            required=True,
        )

    def save(self, request):
        user = super().save(request)
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.save()
        return user