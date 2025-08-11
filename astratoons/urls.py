# astratoons/urls.py

from django.conf import settings
from django.urls import include, path
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from politica.views import politica_de_privacidade_view, dmca_view, termos_de_uso_view
from knox import views as knox_views
from manga import views as manga_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    
    path('avatar/', include('avatar.urls')),
    path('meu-perfil/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('allauth.urls')), 
    
    path('<slug:manga_slug>/doar/', manga_views.donate_to_manga_view, name='donate_to_manga'),
    
    # URLs de Website
    path('manga/', include('manga.urls', namespace='manga')),
    path('novel/', include('novels.urls', namespace='novels')),
    path('subscriptions/', include('subscriptions.urls', namespace='subscriptions')),
    path('paypal/', include('paypal.standard.ipn.urls')),
    path('comments/', include('comments.urls', namespace='comments')),
    path('search/', include('search.urls', namespace='search')),

    # URLs da API para o app móvel
    path('api/manga/', include('manga.api_urls')), # Adicionamos esta linha para a API

    # URLs de Autenticação existentes
    path('api/auth/logout/', knox_views.LogoutView.as_view(), name='knox_api_logout'),
    path('api/auth/logoutall/', knox_views.LogoutAllView.as_view(), name='knox_api_logoutall'),

    path('', include('core.urls', namespace='core')),
    path('politica-de-privacidade/', politica_de_privacidade_view, name='politica_de_privacidade'),
    path('dmca/', dmca_view, name='dmca'),
    path('termos-de-uso/', termos_de_uso_view, name='termos_de_uso'),
    
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns() 
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns