from django.urls import path
from .views import LoginView, LogoutView, MeView, RefreshView, RegisterView, VerifyEmailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('refresh/', RefreshView.as_view(), name='auth-refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('me/', MeView.as_view(), name='auth-me'),
]
