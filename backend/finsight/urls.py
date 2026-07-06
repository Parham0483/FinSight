from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/orgs/', include('apps.organisations.urls')),
    path('api/v1/banking/', include('apps.banking.urls')),
    path('api/v1/transactions/', include('apps.transactions.urls')),
    path('api/v1/categories/', include('apps.categories.urls')),
    path('api/v1/counterparties/', include('apps.counterparties.urls')),
    path('api/v1/forecast/', include('apps.forecasting.urls')),
    path('api/v1/insights/', include('apps.insights.urls')),
    path('api/v1/alerts/', include('apps.alerts.urls')),
    path('api/v1/fx/', include('apps.fx.urls')),
    # Document ingestion — nested under each org
    path('api/v1/orgs/<uuid:org_id>/documents/', include('apps.documents.urls')),
    path('webhooks/', include('apps.banking.webhook_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
