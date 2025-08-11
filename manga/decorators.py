# manga/decorators.py

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def vip_or_staff_required(view_func):
    """
    Decorador que verifica se o usuário está logado e é VIP ou Staff.
    Se não for, redireciona para a página de planos com uma mensagem.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Primeiro, verifica se o usuário está logado
        if not request.user.is_authenticated:
            # Você pode personalizar para onde redirecionar o usuário não logado
            return redirect('account_login') 

        # Verifica se é staff ou superuser
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        # Verifica se tem uma assinatura VIP ativa
        try:
            if request.user.assinatura_vip.esta_ativa:
                return view_func(request, *args, **kwargs)
        except AttributeError:
            # Ocorre se o usuário não tiver o atributo 'assinatura_vip'
            pass
        
        # Se chegou até aqui, o usuário não tem permissão
        messages.error(request, "Apenas assinantes VIP podem acessar este conteúdo.")
        # Redireciona para a página de planos de assinatura
        return redirect('subscriptions:plans') # Verifique se 'subscriptions:plans' é o nome correto da sua rota

    return _wrapped_view