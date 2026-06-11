"""Auth API (architecture §7.4).

Access token returns in the response body (short-lived, held in memory by the
SPA). The refresh token is set in an HttpOnly, Secure, SameSite cookie scoped to
the auth path — never readable by JS, mitigating XSS token theft. Refresh
tokens rotate and the used token is blacklisted on every refresh/logout.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit import services as audit
from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserSerializer,
)

COOKIE = settings.JWT_REFRESH_COOKIE


class LoginThrottle(ScopedRateThrottle):
    scope = "login"


def _set_refresh_cookie(response, refresh: str) -> None:
    response.set_cookie(
        COOKIE,
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
        path=settings.JWT_REFRESH_COOKIE_PATH,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # `authenticate` runs through django-axes for lockout/brute-force protection.
    user = authenticate(
        request,
        username=serializer.validated_data["email"].lower(),
        password=serializer.validated_data["password"],
    )
    if user is None or not user.is_active:
        audit.record(audit.AuditLog.Action.LOGIN_FAILED,
                     target_type="User", target_id=serializer.validated_data["email"])
        return Response({"error": {"code": "invalid_credentials", "message": "Invalid email or password."}},
                        status=status.HTTP_401_UNAUTHORIZED)

    # MFA gate: credentials are correct but a second factor is required. Do NOT
    # issue tokens here — the client must complete /auth/mfa/verify (TOTP) before
    # any session token is granted.
    if getattr(user, "mfa_enabled", False):
        audit.record(audit.AuditLog.Action.LOGIN, target=user, changes={"mfa": "required"})
        return Response(
            {"mfa_required": True, "detail": "Multi-factor verification required.",
             "user_id": user.id},
            status=status.HTTP_200_OK,
        )

    refresh = RefreshToken.for_user(user)
    audit.record(audit.AuditLog.Action.LOGIN, target=user)
    resp = Response({"access": str(refresh.access_token), "user": UserSerializer(user).data})
    _set_refresh_cookie(resp, str(refresh))
    return resp


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh(request):
    token = request.COOKIES.get(COOKIE)
    if not token:
        return Response({"error": {"code": "no_refresh", "message": "Missing refresh token."}},
                        status=status.HTTP_401_UNAUTHORIZED)
    try:
        old = RefreshToken(token)
        user_id = old.payload.get("user_id")
        # Rotate: blacklist the presented token, then issue a fresh pair.
        old.blacklist()
    except TokenError:
        return Response({"error": {"code": "invalid_refresh", "message": "Refresh token invalid or expired."}},
                        status=status.HTTP_401_UNAUTHORIZED)

    from .models import User
    user = User.objects.filter(pk=user_id).first()
    if not user or not user.is_active:
        return Response({"error": {"code": "invalid_refresh", "message": "User unavailable."}},
                        status=status.HTTP_401_UNAUTHORIZED)
    fresh = RefreshToken.for_user(user)
    resp = Response({"access": str(fresh.access_token)})
    _set_refresh_cookie(resp, str(fresh))
    return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    token = request.COOKIES.get(COOKIE)
    if token:
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            pass
    audit.record(audit.AuditLog.Action.LOGOUT, target=request.user)
    resp = Response({"status": "logged_out"})
    resp.delete_cookie(COOKIE, path=settings.JWT_REFRESH_COOKIE_PATH)
    return resp


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = request.user
    if not user.check_password(serializer.validated_data["old_password"]):
        return Response({"error": {"code": "invalid_password", "message": "Current password is incorrect."}},
                        status=status.HTTP_400_BAD_REQUEST)
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    audit.record(audit.AuditLog.Action.UPDATE, target=user, changes={"password": "changed"})
    return Response({"status": "password_changed"})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].lower()
    
    from .models import User
    user = User.objects.filter(email=email, is_active=True).first()
    if user:
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.core.mail import send_mail
        
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{settings.SITE_URL}/reset-password?uid={uid}&token={token}"
        
        subject = "Password Reset Request"
        body = f"Hello,\n\nYou requested a password reset. Please use the following link to reset your password:\n\n{reset_link}\n\nIf you did not request this, please ignore this email.\n"
        
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        audit.record(audit.AuditLog.Action.UPDATE, target=user, changes={"password_reset": "requested"})
        
    return Response({"status": "password_reset_sent"})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    uidb64 = serializer.validated_data["uid"]
    token = serializer.validated_data["token"]
    new_password = serializer.validated_data["new_password"]
    
    from django.utils.http import urlsafe_base64_decode
    from django.utils.encoding import force_str
    from django.contrib.auth.tokens import default_token_generator
    from .models import User
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid, is_active=True).first()
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
        
    if user is not None and default_token_generator.check_token(user, token):
        user.set_password(new_password)
        user.save(update_fields=["password"])
        audit.record(audit.AuditLog.Action.UPDATE, target=user, changes={"password_reset": "confirmed"})
        return Response({"status": "password_reset_confirmed"})
    else:
        return Response({"error": {"code": "invalid_token", "message": "The reset token is invalid or expired."}},
                        status=status.HTTP_400_BAD_REQUEST)

