import logging
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.http import JsonResponse
from django.views import View

# Imports corrigidos e adicionados
from subscriptions.models import AssinaturaUsuario, PlanoVIP
from novels.models import Favorite as FavoriteNovel
from manga.models import Favorite as FavoriteManga
from .models import Profile, CosmeticBadge, UserBadge
from .forms import (
    CustomUserCreationForm,
    UserProfileEditForm,
    ProfileInfoForm,
    ProfileSiteAvatarForm,
    ManualLoginForm,
)

from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.serializers import AuthTokenSerializer
from knox.models import AuthToken
from .serializers import UserSerializer 

logger = logging.getLogger(__name__)


class ApiLoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, format=None):
        serializer = AuthTokenSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        instance, token = AuthToken.objects.create(user)
        return Response({
            "user": UserSerializer(user).data,
            "expiry": instance.expiry,
            "token": token
        })

def manual_login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = ManualLoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['login'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user)
                return redirect('core:home')
            else:
                messages.error(request, 'Usuário ou senha inválidos.')
                return redirect('accounts:account_login')
    else:
        form = ManualLoginForm()
    
    return render(request, 'account/login.html', {'form': form})

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('account_login')
    template_name = 'account/signup.html'
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)
    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, _("Cadastro realizado com sucesso! Por favor, faça o login."))
        return redirect(self.success_url)

class LogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "Você saiu da sua conta.")
        return redirect('core:home')

logout_view = LogoutView.as_view()

@login_required
def profile_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    user_subscription = None
    try:
        # Acessando via o nome correto do related_name
        user_subscription = request.user.assinatura_vip
    except AssinaturaUsuario.DoesNotExist:
        pass
    context = {
        'user': request.user,
        'profile': profile,
        'user_subscription': user_subscription,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def saved_mangas_view(request):
    favorite_novels = FavoriteNovel.objects.filter(user=request.user).select_related('novel')
    favorite_mangas = FavoriteManga.objects.filter(user=request.user).select_related('manga')
    novels_list_typed = []
    for fav in favorite_novels:
        fav.item_type = 'novel'; fav.content_object = fav.novel; novels_list_typed.append(fav)
    mangas_list_typed = []
    for fav in favorite_mangas:
        fav.item_type = 'manga'; fav.content_object = fav.manga; mangas_list_typed.append(fav)
    all_favorites = sorted(novels_list_typed + mangas_list_typed, key=lambda x: x.favorited_at if hasattr(x, 'favorited_at') else timezone.now(), reverse=True)
    paginator = Paginator(all_favorites, 12)
    page_number = request.GET.get('page')
    favorites_page_obj = paginator.get_page(page_number)
    context = {'favorites_list': favorites_page_obj}
    return render(request, 'accounts/saved.html', context)

@login_required
def profile_settings_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    user = request.user
    
    if request.method == 'POST':
        user_form = UserProfileEditForm(request.POST, instance=user)
        profile_form = ProfileInfoForm(request.POST, instance=profile, user=user)
        avatar_form = ProfileSiteAvatarForm(request.POST, request.FILES, instance=profile)

        if 'save_profile_info' in request.POST:
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, _('Suas informações foram atualizadas!'))
                return redirect('accounts:profile_edit')
            else:
                messages.error(request, _('Por favor, corrija os erros abaixo.'))

        elif 'save_avatar' in request.POST:
            if avatar_form.is_valid():
                avatar_form.save()
                messages.success(request, _('Seu avatar foi atualizado!'))
                return redirect('accounts:profile_edit')
            else:
                messages.error(request, _('Não foi possível atualizar o avatar.'))

    else:
        user_form = UserProfileEditForm(instance=user)
        profile_form = ProfileInfoForm(instance=profile, user=user)
        avatar_form = ProfileSiteAvatarForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'avatar_form': avatar_form,
        'profile': profile,
    }
    return render(request, 'accounts/profile_edit.html', context)

@login_required
@transaction.atomic
def update_profile_avatar(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == 'POST':
        form = ProfileSiteAvatarForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _('Avatar atualizado com sucesso!'))
        else:
            error_message_list = []
            for field, errors_for_field in form.errors.as_data().items():
                for error in errors_for_field:
                    message_text = error.message
                    if isinstance(message_text, list): message_text = '; '.join(message_text)
                    if field != '__all__':
                        field_obj = form.fields.get(field)
                        field_label = field_obj.label if field_obj and field_obj.label else field.replace('_', ' ').capitalize()
                        error_message_list.append(f"{field_label}: {message_text}")
                    else: error_message_list.append(message_text)
            if not error_message_list: error_message_list.append(_('Não foi possível atualizar o avatar. Verifique o arquivo.'))
            for msg_txt_loop in error_message_list: messages.error(request, msg_txt_loop, extra_tags='avatar_upload_error')
    return redirect('accounts:profile_edit')

@login_required
@transaction.atomic
def delete_account_view(request):
    if request.method == 'POST':
        user_to_delete = request.user
        try:
            username_for_message = user_to_delete.username
            logout(request)
            user_to_delete.delete()
            messages.success(request, _('A conta de "%(username)s" foi excluída permanentemente.') % {'username': username_for_message})
            return redirect('core:home')
        except Exception as e:
            logger.exception(f"Erro crítico ao tentar deletar o usuário {getattr(user_to_delete, 'username', 'desconhecido')}: {e}")
            messages.error(request, _('Ocorreu um erro crítico ao tentar excluir sua conta. Por favor, contate o suporte.'))
            return redirect('account_login')
    return redirect('accounts:profile_edit')

@login_required
def badge_store_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            badge_id = int(data.get('badge_id'))
        except (json.JSONDecodeError, TypeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Requisição inválida.'}, status=400)

        try:
            badge_to_buy = CosmeticBadge.objects.get(pk=badge_id, is_staff_only=False)
        except CosmeticBadge.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Este badge não existe ou não está à venda.'}, status=404)

        try:
            with transaction.atomic():
                profile = Profile.objects.select_for_update().get(user=request.user)

                if UserBadge.objects.filter(user=request.user, badge=badge_to_buy).exists():
                    return JsonResponse({'status': 'error', 'message': 'Você já possui este badge.'}, status=400)

                if profile.moedas < badge_to_buy.price:
                    return JsonResponse({'status': 'error', 'message': 'Moedas insuficientes.'}, status=400)

                profile.moedas = F('moedas') - badge_to_buy.price
                profile.save()

                UserBadge.objects.create(user=request.user, badge=badge_to_buy)
                
                if badge_to_buy.is_vip_badge:
                    plano_via_badge = PlanoVIP.objects.get(nome="VIP via Moedas")
                    
                    # ===============================================
                    # AQUI ESTÁ A CORREÇÃO FINAL
                    # Trocamos 'user=' por 'usuario=' para corresponder ao seu modelo de dados
                    # ===============================================
                    assinatura, created = AssinaturaUsuario.objects.get_or_create(
                        usuario=request.user,
                        defaults={
                            'plano': plano_via_badge, 
                            'data_inicio': timezone.now()
                        }
                    )
                    
                    if created:
                        assinatura.data_fim = timezone.now() + timedelta(days=plano_via_badge.duracao_dias)
                    else:
                        if assinatura.data_fim and assinatura.data_fim > timezone.now():
                            assinatura.data_fim += timedelta(days=plano_via_badge.duracao_dias)
                        else:
                            assinatura.data_fim = timezone.now() + timedelta(days=plano_via_badge.duracao_dias)
                    
                    assinatura.plano = plano_via_badge
                    assinatura.save()

                    logger.info(f"Assinatura VIP ativada/estendida para '{request.user.username}' via compra do badge '{badge_to_buy.name}'.")

                profile.refresh_from_db()

                return JsonResponse({
                    'status': 'success',
                    'message': f'Badge "{badge_to_buy.name}" comprado com sucesso!',
                    'new_balance': profile.moedas
                })
        except PlanoVIP.DoesNotExist:
            logger.error("ERRO DE CONFIGURAÇÃO CRÍTICO: O plano 'VIP via Moedas' não foi encontrado no banco de dados.")
            return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro de configuração no servidor.'}, status=500)
        except Exception as e:
            logger.error(f"Erro inesperado ao comprar badge: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro de conexão. Tente novamente.'}, status=500)

    all_badges = CosmeticBadge.objects.filter(is_staff_only=False).order_by('price')
    owned_badge_ids = UserBadge.objects.filter(user=request.user).values_list('badge_id', flat=True)
    
    context = {
        'all_badges': all_badges,
        'owned_badge_ids': set(owned_badge_ids),
    }
    return render(request, 'accounts/badge_store.html', context)