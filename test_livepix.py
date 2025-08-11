import logging
import requests
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from wagtail.models import Site

from .models import PlanoVIP, AssinaturaUsuario
from core.models import GlobalSettings

logger = logging.getLogger(__name__)
User = get_user_model()

def plans_page_view(request):
    planos_ativos = PlanoVIP.objects.filter(ativo=True).order_by('preco')
    context = {'planos': planos_ativos}
    return render(request, 'subscriptions/plans_page.html', context)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_view(request):
    try:
        plano_id = request.data.get('plano_id')
        if not plano_id:
            return Response({'error': 'ID do plano não fornecido.'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return Response({'error': 'Requisição inválida.'}, status=status.HTTP_400_BAD_REQUEST)

    plano = get_object_or_404(PlanoVIP, pk=plano_id, ativo=True)
    
    # =========================================================================
    # TESTE DE VERDADE: VAMOS IGNORAR O BANCO DE DADOS E USAR AS CHAVES NA MÃO
    # SUBSTITUA AS CREDENCIAIS ABAIXO PELAS SUAS!
    # =========================================================================
    
    # Comentamos as linhas que buscam do banco de dados para o teste
    # current_site = Site.find_for_request(request._request)
    # global_settings = GlobalSettings.for_site(current_site)
    # client_id = getattr(global_settings, 'livepix_client_id', None)
    # client_secret = getattr(global_settings, 'livepix_client_secret', None)

    client_id = "COLE_SEU_CLIENT_ID_AQUI"
    client_secret = "COLE_SEU_CLIENT_SECRET_AQUI"
    
    print("="*60)
    print("[DEBUG] USANDO CREDENCIAIS HARDCODED NO CÓDIGO!")
    print(f"[DEBUG] Client ID: '{client_id}'")
    print(f"[DEBUG] Client Secret: '...{client_secret[-4:] if client_secret and 'SEU_CLIENT' not in client_secret else 'NÃO EDITADO'}'")
    print("="*60)
    
    # =========================================================================
    
    if not client_id or "SEU_CLIENT" in client_id:
        # Se você não editou as chaves, vamos parar aqui para evitar erro
        logger.error("ERRO DE TESTE: As credenciais hardcoded no arquivo subscriptions/views.py não foram editadas.")
        return Response({'error': 'ERRO: Você precisa editar as credenciais hardcoded no arquivo views.py'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    token_url = "https://oauth.livepix.gg/oauth2/token"
    token_payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    try:
        token_response = requests.post(token_url, data=token_payload, timeout=15) 
        
        if token_response.status_code != 200:
            logger.error(
                f"LivePix API: Falha ao obter token. Status: {token_response.status_code}. "
                f"Resposta: {token_response.text}"
            )
            token_response.raise_for_status()

        access_token = token_response.json().get("access_token")
        if not access_token:
            raise ValueError("Token de acesso não encontrado na resposta.")
            
    except requests.RequestException as e:
        logger.error(f"LivePix API: Erro na etapa de autenticação: {e}")
        return Response({'error': 'Erro de comunicação com o gateway de pagamento.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    charge_url = "https://api.livepix.gg/v1/charges"
    charge_headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    charge_payload = {
        "amount": int(plano.preco * 100),
        "description": f"Assinatura do plano '{plano.nome}'",
        "correlationID": f"VIP-{request.user.id}-{plano.id}-{int(timezone.now().timestamp())}",
        "info": f"ID do Usuário: {request.user.id}, Plano: {plano.nome}",
        "customer": {"name": request.user.username, "email": request.user.email}
    }
    
    try:
        charge_response = requests.post(charge_url, json=charge_payload, headers=charge_headers, timeout=15)
        charge_response.raise_for_status()
        charge_data = charge_response.json()
        
        checkout_url = charge_data.get('paymentLink')
        
        if not checkout_url:
            logger.error("LivePix API: 'paymentLink' não foi encontrado na resposta da cobrança.")
            return Response({'error': 'Falha ao obter o link de pagamento do gateway.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'status': 'success',
            'checkoutUrl': checkout_url
        }, status=status.HTTP_200_OK)

    except requests.RequestException as e:
        error_text = e.response.text if hasattr(e, 'response') and e.response else str(e)
        logger.error(f"LivePix API: Erro ao criar cobrança: {error_text}")
        return Response({'error': 'Não foi possível gerar a cobrança Pix.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def livepix_webhook_view(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body)
        logger.info(f"Webhook LivePix: Notificação recebida: {data}")

        if data.get('eventName') == 'TRANSACTION_RECEIVED' or data.get('status') == 'PAID':
            charge = data.get('transaction', data.get('charge', {}))
            correlation_id = charge.get('correlationID', '')
            
            if not correlation_id:
                logger.warning("Webhook LivePix: correlationID não encontrado no payload.")
                return HttpResponse(status=200)

            parts = correlation_id.split('-')
            if len(parts) == 4 and parts[0] == 'VIP':
                user_id = int(parts[1])
                plano_id = int(parts[2])
                
                try:
                    user = User.objects.get(pk=user_id)
                    plano = PlanoVIP.objects.get(pk=plano_id)

                    assinatura, created = AssinaturaUsuario.objects.get_or_create(
                        usuario=user,
                        defaults={
                            'plano': plano,
                            'data_inicio': timezone.now(),
                            'data_fim': timezone.now() + timezone.timedelta(days=plano.duracao_dias)
                        }
                    )

                    if not created:
                        assinatura.estender_assinatura(plano)
                    
                    logger.info(f"Assinatura VIP ativada/estendida para o usuário '{user.username}' com o plano '{plano.nome}'.")

                except (User.DoesNotExist, PlanoVIP.DoesNotExist):
                    logger.error(f"Webhook LivePix: Usuário ou Plano não encontrado no DB para o correlationID: {correlation_id}")
                except Exception as e:
                    logger.error(f"Webhook LivePix: Erro ao processar assinatura para {correlation_id}: {e}")

    except json.JSONDecodeError:
        logger.error("Webhook LivePix: Erro ao decodificar JSON do corpo da requisição.")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Webhook LivePix: Erro inesperado ao processar webhook: {e}")

    return HttpResponse(status=200)


@login_required
def payment_success_view(request):
    messages.success(request, _("Pagamento confirmado! Seu acesso VIP foi ativado."))
    return redirect('accounts:profile')