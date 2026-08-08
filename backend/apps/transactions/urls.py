from django.urls import path

from .views import (
    TransactionCsvImportView,
    TransactionDetailView,
    TransactionListCreateView,
    TransactionRollupView,
)

urlpatterns = [
    path('', TransactionListCreateView.as_view(), name='transaction-list'),
    path('import-csv/', TransactionCsvImportView.as_view(), name='transaction-import-csv'),
    path('rollup/', TransactionRollupView.as_view(), name='transaction-rollup'),
    path('<uuid:pk>/', TransactionDetailView.as_view(), name='transaction-detail'),
]
