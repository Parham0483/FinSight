from django.urls import path
from .views import (
    DocumentConfirmView,
    DocumentDetailView,
    DocumentListUploadView,
    DocumentRejectView,
    DocumentReprocessView,
    StorageSettingsView,
)

# Mounted at /api/v1/orgs/{org_id}/documents/
urlpatterns = [
    path('', DocumentListUploadView.as_view(), name='document-list'),
    path('storage/', StorageSettingsView.as_view(), name='document-storage-settings'),
    path('<uuid:doc_id>/', DocumentDetailView.as_view(), name='document-detail'),
    path('<uuid:doc_id>/confirm/', DocumentConfirmView.as_view(), name='document-confirm'),
    path('<uuid:doc_id>/reject/', DocumentRejectView.as_view(), name='document-reject'),
    path('<uuid:doc_id>/reprocess/', DocumentReprocessView.as_view(), name='document-reprocess'),
]
