# subscriptions/views.py

import logging
import requests
import json
import uuid

from django.db import transaction
from django.db.models import F
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from wagtail.models import Site
from django.urls import reverse
from allauth.socialaccount.models import SocialAccount

from knox.auth import TokenAuthentication
from knox.models import AuthToken

from .models import PlanoVIP, AssinaturaUsuario, Transacao, CoinPackage, PaypalOrder
from core.models import GlobalSettings

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required 
def plans_page_view(request):
    planos_ativos = PlanoVIP.objects.filter(ativo=True).order_by('price')
    
    global_settings = GlobalSettings.for_site(Site.find_for_request(request))
    
    if global_settings.default_currency == 'USD':
        for plano in planos_ativos:
            order = PaypalOrder.objects.create(
                user=request.user,
                subscription_plan=plano,
                amount=plano.price
            )
            plano.invoice_id = order.invoice_id

    instance, token = AuthToken.objects.create(request.user)
    
    context = {
        'planos': planos_ativos,
        'knox_token': token,
        # --- ATUALIZAÇÃO: Adicionando o email do PayPal ao contexto ---
        'paypal_receiver_email': global_settings.paypal_receiver_email,
    }
    return render(request, 'subscriptions/plans_page.html', context)


def assign_discord_role(user, global_settings):
    bot_token = getattr(global_settings, 'discord_bot_token', None)
    guild_id = getattr(global_settings, 'discord_guild_id', None)
    role_id = getattr(global_settings, 'discord_vip_role_id', None)

    if not all([bot_token, guild_id, role_id]):
        logger.error(f"Configurações do Discord incompletas para atribuir cargo ao usuário {user.id}.")
        return

    try:
        social_account = SocialAccount.objects.get(user=user, provider='discord')
        discord_user_id = social_account.uid
    except SocialAccount.DoesNotExist:
        logger.warning(f"Usuário {user.id} não tem uma conta do Discord conectada. Não foi possível atribuir o cargo.")
        return

    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_user_id}/roles/{role_id}"
    headers = {"Authorization": f"Bot {bot_token}"}
    
    try:
        response = requests.put(url, headers=headers)
        response.raise_for_status()
        logger.info(f"Cargo VIP atribuído com sucesso ao usuário {user.id} (Discord ID: {discord_user_id})")
    except requests.RequestException as e:
        error_details = e.response.text if e.response else str(e)
        logger.error(f"Falha ao atribuir cargo no Discord para o usuário {user.id}. Erro: {error_details}")


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_payment_view(request):
    try:
        plano_id = request.data.get('plano_id')
        plano = get_object_or_404(PlanoVIP, pk=plano_id, ativo=True)
    except (ValueError, TypeError):
        return Response({'error': _('ID do plano inválido.')}, status=status.HTTP_400_BAD_REQUEST)

    global_settings = GlobalSettings.for_site(Site.find_for_request(request._request))
    client_id = getattr(global_settings, 'livepix_client_id', None)
    client_secret = getattr(global_settings, 'livepix_client_secret', None)
    
    if not client_id or not client_secret:
        logger.error("Credenciais LivePix (client_id ou client_secret) não configuradas.")
        return Response({'error': _('Erro de configuração do servidor.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    token_url = "https://oauth.livepix.gg/oauth2/token"
    token_payload = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": "payments:write"}
    
    try:
        token_response = requests.post(token_url, data=token_payload, timeout=15)
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
    except requests.RequestException:
        logger.error("Falha ao obter token de acesso da LivePix.")
        return Response({'error': _('Erro de comunicação com o gateway de pagamento.')}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    payment_url = "https://api.livepix.gg/v2/payments"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    valor_em_centavos = int(plano.price * 100)
    success_redirect_url = request.build_absolute_uri(reverse('subscriptions:payment_success'))
    payload = {"amount": valor_em_centavos, "currency": "BRL", "redirectUrl": success_redirect_url}

    try:
        payment_response = requests.post(payment_url, json=payload, headers=headers, timeout=15)
        payment_response.raise_for_status()
        payment_data = payment_response.json().get('data', {})
        livepix_reference = payment_data.get('reference')
        checkout_url = payment_data.get('redirectUrl')

        if not livepix_reference or not checkout_url:
            raise ValueError("Resposta da API de pagamento da LivePix incompleta.")

        Transacao.objects.create(
            usuario=request.user,
            plano=plano,
            livepix_reference=livepix_reference,
            status='PENDING'
        )
        logger.info(f"Transação PENDENTE criada para user {request.user.id}. Ref LivePix: {livepix_reference}")

        return Response({'status': 'success', 'redirectUrl': checkout_url}, status=status.HTTP_200_OK)

    except (requests.RequestException, ValueError, KeyError) as e:
        logger.error(f"LivePix API (v2): Erro ao criar pagamento: {e}")
        return Response({'error': _('Não foi possível gerar a cobrança Pix.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def livepix_webhook_view(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body)
        logger.info(f"Webhook LivePix (v2): Notificação recebida: {data}")

        resource = data.get('resource', {})
        livepix_reference = resource.get('reference')

        if data.get('event') == 'new' and resource.get('type') == 'payment' and livepix_reference:
            
            with transaction.atomic():
                transacao = Transacao.objects.select_for_update().filter(livepix_reference=livepix_reference, status='PENDING').first()

                if transacao:
                    user = transacao.usuario
                    transacao.status = 'PAID'
                    
                    if transacao.plano:
                        plano = transacao.plano
                        assinatura, created = AssinaturaUsuario.objects.get_or_create(
                            usuario=user,
                            defaults={'plano': plano, 'data_inicio': timezone.now(), 'data_fim': timezone.now() + timezone.timedelta(days=plano.duracao_dias)}
                        )
                        if not created:
                            assinatura.estender_assinatura(plano)
                        
                        transacao.save()
                        logger.info(f"Assinatura ativada para '{user.username}' via webhook. Ref: {livepix_reference}")

                        global_settings = GlobalSettings.for_site(Site.objects.first())
                        assign_discord_role(user, global_settings)
                    
                    elif transacao.pacote_moedas:
                        package = transacao.pacote_moedas
                        user.profile.moedas = F('moedas') + package.amount
                        user.profile.save()
                        transacao.save()
                        logger.info(f"{package.amount} moedas adicionadas para '{user.username}'. Ref: {livepix_reference}")

                else:
                    logger.warning(f"Webhook recebido para transação já processada ou desconhecida: {livepix_reference}")
    
    except Exception as e:
        logger.error(f"Webhook LivePix: Erro inesperado: {e}", exc_info=True)

    return HttpResponse(status=200)


@login_required
def payment_success_view(request):
    messages.success(request, _("Obrigado pelo seu apoio! Seu pagamento está sendo processado e sua assinatura ou moedas serão ativadas em breve."))
    return redirect('accounts:profile')


@login_required
def coin_store_view(request):
    packages = CoinPackage.objects.filter(is_active=True).order_by('order')
    
    global_settings = GlobalSettings.for_site(Site.find_for_request(request))
    
    if global_settings.default_currency == 'USD':
        for package in packages:
            order = PaypalOrder.objects.create(
                user=request.user,
                coin_package=package,
                amount=package.price
            )
            package.invoice_id = order.invoice_id
            
    instance, token = AuthToken.objects.create(request.user)
    context = {
        'packages': packages,
        'knox_token': token,
        # --- ATUALIZAÇÃO: Adicionando o email do PayPal ao contexto ---
        'paypal_receiver_email': global_settings.paypal_receiver_email,
    }
    return render(request, 'subscriptions/coin_store.html', context)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_coin_payment_view(request):
    try:
        package_id = request.data.get('package_id')
        package = get_object_or_404(CoinPackage, pk=package_id, is_active=True)
    except (ValueError, TypeError):
        return Response({'error': _('ID do pacote inválido.')}, status=status.HTTP_400_BAD_REQUEST)

    global_settings = GlobalSettings.for_site(Site.find_for_request(request._request))
    client_id = getattr(global_settings, 'livepix_client_id', None)
    client_secret = getattr(global_settings, 'livepix_client_secret', None)
    
    if not client_id or not client_secret:
        logger.error("Credenciais LivePix (client_id ou client_secret) não configuradas.")
        return Response({'error': _('Erro de configuração do servidor.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    token_url = "https://oauth.livepix.gg/oauth2/token"
    token_payload = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": "payments:write"}
    
    try:
        token_response = requests.post(token_url, data=token_payload, timeout=15)
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
    except requests.RequestException:
        logger.error("Falha ao obter token de acesso da LivePix.")
        return Response({'error': _('Erro de comunicação com o gateway de pagamento.')}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    payment_url = "https://api.livepix.gg/v2/payments"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    valor_em_centavos = int(package.price * 100)
    success_redirect_url = request.build_absolute_uri(reverse('accounts:profile'))
    payload = {"amount": valor_em_centavos, "currency": "BRL", "redirectUrl": success_redirect_url, "description": f"Compra de {package.amount} moedas"}

    try:
        payment_response = requests.post(payment_url, json=payload, headers=headers, timeout=15)
        payment_response.raise_for_status()
        payment_data = payment_response.json().get('data', {})
        livepix_reference = payment_data.get('reference')
        checkout_url = payment_data.get('redirectUrl')

        if not livepix_reference or not checkout_url:
            raise ValueError("Resposta da API de pagamento da LivePix incompleta.")

        Transacao.objects.create(
            usuario=request.user,
            plano=None,
            pacote_moedas=package,
            livepix_reference=livepix_reference,
            status='PENDING'
        )
        logger.info(f"Cobrança de MOEDAS PENDENTE criada para user {request.user.id}. Ref LivePix: {livepix_reference}")

        return Response({'status': 'success', 'redirectUrl': checkout_url}, status=status.HTTP_200_OK)

    except (requests.RequestException, ValueError, KeyError) as e:
        logger.error(f"LivePix API (v2): Erro ao criar pagamento de MOEDAS: {e}")
        return Response({'error': _('Não foi possível gerar a cobrança Pix.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)