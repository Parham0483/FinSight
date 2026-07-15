from django.urls import path

from .views import (
    CounterpartyDetailView,
    CounterpartyListCreateView,
    CounterpartyMergeView,
)

urlpatterns = [
    path('', CounterpartyListCreateView.as_view(), name='counterparty-list'),
    path('<uuid:pk>/', CounterpartyDetailView.as_view(), name='counterparty-detail'),
    path('<uuid:pk>/merge/', CounterpartyMergeView.as_view(), name='counterparty-merge'),
]
