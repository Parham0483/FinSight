from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/orgs/', include('apps.organisations.urls')),
    path('api/v1/banking/', include('apps.banking.urls')),
    path('api/v1/transactions/', include('apps.transactions.urls')),
    path('api/v1/forecast/', include('apps.forecasting.urls')),
    path('api/v1/insights/', include('apps.insights.urls')),
    path('api/v1/customers/', include('apps.customers.urls')),
    path('api/v1/alerts/', include('apps.alerts.urls')),
    path('api/v1/fx/', include('apps.fx.urls')),
    path('webhooks/', include('apps.banking.webhook_urls')),
]
