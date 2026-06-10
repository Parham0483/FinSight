from django.urls import path
from .views import OrgDetailView, OrgListCreateView

urlpatterns = [
    path('', OrgListCreateView.as_view(), name='org-list-create'),
    path('<uuid:pk>/', OrgDetailView.as_view(), name='org-detail'),
]
