# accounts/urls.py (VERSÃO CORRIGIDA E FINAL)

from django.urls import path, reverse_lazy, include
from . import views
from django.contrib.auth import views as auth_views
from novels import views as novel_views # Mantido se você usa para o toggle_favorite

# A importação 'from allauth.account.views import LoginView' foi removida, 
# pois a rota de login principal agora é gerenciada pelo 'allauth.urls'.

app_name = 'accounts'

urlpatterns = [
    # Rotas de interface para o usuário (páginas web)
    path('signup/', views.SignUpView.as_view(), name='account_signup'),
    path('profile/', views.profile_view, name='profile'),
    path('profile_edit/', views.profile_settings_view, name='profile_edit'),
    path('profile/avatar/update/', views.update_profile_avatar, name='update_profile_avatar'),
    path('salvos/', views.saved_mangas_view, name='saved_mangas_list'),
    path('profile/delete/', views.delete_account_view, name='delete_account'),
    path('loja/badges/', views.badge_store_view, name='badge_store'),

    # Rotas para mudança de senha
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change_form.html', 
        success_url=reverse_lazy('accounts:password_change_done')
    ), name='change_password'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view( template_name='accounts/password_change_done.html' ), name='password_change_done'),
    
    # --- Suas URLs de API ---
    path('api/toggle-favorite/', novel_views.api_toggle_favorite_view, name='api_toggle_favorite'),
    path('api/login/', views.ApiLoginView.as_view(), name='knox_login'),
    path('', include('allauth.urls')),
]