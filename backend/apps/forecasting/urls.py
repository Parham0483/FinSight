from django.urls import path
from .views import ForecastMaturityView

urlpatterns = [
    path('orgs/<uuid:org_id>/maturity/', ForecastMaturityView.as_view(), name='forecast-maturity'),
]

