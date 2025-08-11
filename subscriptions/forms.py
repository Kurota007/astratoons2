# Em manga/forms.py

from django import forms
from django.contrib.auth.models import User

class CoinAdditionForm(forms.Form):
    # Campo para selecionar um usuário de uma lista.
    # Exibirá os usuários pelo nome de usuário em ordem alfabética.
    user = forms.ModelChoiceField(
        queryset=User.objects.order_by('username'),
        label="Selecione o Usuário"
    )

    # Campo para digitar a quantidade de moedas a serem adicionadas.
    amount = forms.IntegerField(
        label="Quantidade de Moedas a Adicionar",
        min_value=1
    )