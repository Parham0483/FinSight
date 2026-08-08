from django.urls import path
from .views import CombinedForecastView, ForecastMaturityView

urlpatterns = [
    path('orgs/<uuid:org_id>/maturity/', ForecastMaturityView.as_view(), name='forecast-maturity'),
    path('orgs/<uuid:org_id>/combined/', CombinedForecastView.as_view(), name='forecast-combined'),
]

