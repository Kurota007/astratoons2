# politica/views.py
from django.shortcuts import render

def politica_de_privacidade_view(request):
    """
    Esta view renderiza o template da Política de Privacidade.
    """
    # Renomeamos o template para ser mais específico
    return render(request, 'politica/politica_de_privacidade.html')


def dmca_view(request):
    """
    Esta view renderiza o template de DMCA.
    """
    return render(request, 'politica/dmca.html')


def termos_de_uso_view(request):
    """
    Esta view renderiza o template de Termos de Uso.
    """
    return render(request, 'politica/termos_de_uso.html')