# subscriptions/signals.py

from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# Importa o sinal que o django-paypal envia após validar uma notificação
from paypal.standard.ipn.signals import valid_ipn_received
# Importa o status de pagamento "Completed"
from paypal.standard.models import ST_PP_COMPLETED

# Importa os modelos do seu projeto que serão usados
from accounts.models import Profile
# --- CORREÇÃO: Usando os nomes corretos dos modelos ---
from .models import PlanoVIP, CoinPackage, PaypalOrder

@receiver(valid_ipn_received)
def handle_paypal_payment(sender, **kwargs):
    """
    Esta função é executada toda vez que o PayPal envia uma notificação
    de pagamento bem-sucedida (IPN - Instant Payment Notification).
    """
    ipn_obj = sender  # O objeto IPN contém todos os dados da transação

    # --- VERIFICAÇÕES DE SEGURANÇA CRÍTICAS ---

    # 1. O pagamento foi realmente concluído?
    if ipn_obj.payment_status != ST_PP_COMPLETED:
        return

    # 2. O pagamento foi enviado para a nossa conta de vendedor correta?
    if ipn_obj.receiver_email != settings.PAYPAL_RECEIVER_EMAIL:
        print(f"ALERTA DE SEGURANÇA: Email do destinatário incorreto: {ipn_obj.receiver_email}")
        return

    # 3. O pedido existe no nosso banco de dados?
    try:
        order = PaypalOrder.objects.get(invoice_id=ipn_obj.invoice)
    except PaypalOrder.DoesNotExist:
        print(f"ALERTA DE SEGURANÇA: Pedido com invoice ID '{ipn_obj.invoice}' não encontrado.")
        return

    # 4. Este pedido já foi processado antes?
    if order.is_completed:
        return

    # --- FIM DAS VERIFICAÇÕES DE SEGURANÇA ---


    # --- LÓGICA DE NEGÓCIO: ENTREGAR O PRODUTO ---

    produto_entregue = False

    # Verifica se a compra foi de um PLANO VIP
    if order.subscription_plan:
        plano = order.subscription_plan
        # --- CORREÇÃO: Usando o campo de preço unificado 'price' ---
        if float(ipn_obj.mc_gross) == float(plano.price) and ipn_obj.mc_currency == 'USD':
            profile = Profile.objects.get(user=order.user)
            
            # Lógica para adicionar dias de VIP (assumindo que Profile tem 'vip_expiration_date')
            # Você pode precisar adaptar esta parte ao seu modelo AssinaturaUsuario
            if hasattr(profile, 'vip_expiration_date') and profile.vip_expiration_date and profile.vip_expiration_date > timezone.now():
                profile.vip_expiration_date += timedelta(days=plano.duracao_dias)
            else:
                profile.vip_expiration_date = timezone.now() + timedelta(days=plano.duracao_dias)
            
            profile.save()
            produto_entregue = True
            print(f"Sucesso: Assinatura VIP de {plano.duracao_dias} dias adicionada para {order.user.username}")

    # Verifica se a compra foi de um PACOTE DE MOEDAS
    elif order.coin_package:
        pacote = order.coin_package
        # --- CORREÇÃO: Usando o campo de preço unificado 'price' ---
        if float(ipn_obj.mc_gross) == float(pacote.price) and ipn_obj.mc_currency == 'USD':
            profile = Profile.objects.get(user=order.user)
            profile.moedas += pacote.amount
            profile.save()
            produto_entregue = True
            print(f"Sucesso: {pacote.amount} moedas adicionadas para {order.user.username}")

    # Se o produto foi entregue com sucesso, marca o pedido como concluído
    if produto_entregue:
        order.is_completed = True
        # Renomeei o campo transaction_id para corresponder ao modelo que montamos
        order.paypal_transaction_id = ipn_obj.txn_id 
        order.save()