import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailVerificationToken, User
from .serializers import (
    EmailVerifySerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)


def _set_auth_cookies(response: Response, refresh: RefreshToken) -> None:
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response.set_cookie(
        'access_token',
        access_token,
        max_age=15 * 60,
        httponly=True,
        samesite='Lax',
        secure=False,  # Set True in production behind HTTPS
    )
    response.set_cookie(
        'refresh_token',
        refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        samesite='Lax',
        secure=False,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')


class RegisterView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = serializer.save()

        # Create verification token (expires in 24h)
        token = secrets.token_urlsafe(32)
        EmailVerificationToken.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Send verification email
        from django.core.mail import send_mail
        from django.conf import settings
        verify_url = f'{request.scheme}://{request.get_host()}/api/v1/auth/verify-email/?token={token}'
        send_mail(
            'Verify your FinSight account',
            f'Click to verify your email: {verify_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )

        return Response(
            {'detail': 'Account created. Check your email to verify.'},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user: User = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        response = Response(UserSerializer(user).data)
        _set_auth_cookies(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get('refresh_token')
        if not raw_refresh:
            return Response({'detail': 'No refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(raw_refresh)
            response = Response({'detail': 'Token refreshed.'})
            _set_auth_cookies(response, refresh)
            return response
        except TokenError:
            return Response({'detail': 'Invalid or expired refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get('refresh_token')
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass

        response = Response({'detail': 'Logged out.'})
        _clear_auth_cookies(response)
        return response


class VerifyEmailView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_str = serializer.validated_data['token']
        try:
            token = EmailVerificationToken.objects.select_related('user').get(
                token=token_str,
                used=False,
                expires_at__gt=timezone.now(),
            )
        except EmailVerificationToken.DoesNotExist:
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        token.used = True
        token.save(update_fields=['used'])
        token.user.is_verified = True
        token.user.save(update_fields=['is_verified'])

        return Response({'detail': 'Email verified. You can now log in.'})

    def get(self, request: Request) -> Response:
        """Support GET for email link click (token in query param)."""
        token_str = request.query_params.get('token', '')
        return self.post(Request(request._request.__class__('POST', '/'), data={'token': token_str}))


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)

    def patch(self, request: Request) -> Response:
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
