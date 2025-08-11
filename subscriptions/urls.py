# subscriptions/urls.py

from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    # O nome 'plans_page' deve corresponder ao que é usado nos templates.
    path('plans/', views.plans_page_view, name='plans_page'),
    path('api/create-payment/', views.create_payment_view, name='create_payment'),
    path('webhook/livepix/', views.livepix_webhook_view, name='livepix_webhook'),
    path('payment/success/', views.payment_success_view, name='payment_success'),
    path('loja/moedas/', views.coin_store_view, name='coin_store'),
    
    path('api/create-coin-payment/', views.create_coin_payment_view, name='create_coin_payment'),
]