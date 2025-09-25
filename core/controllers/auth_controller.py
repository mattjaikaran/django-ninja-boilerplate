import logging
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from ninja_extra import api_controller, http_post

from api.decorators import handle_exceptions, log_api_call
from core.models import OneTimePassword
from core.schemas import PasswordlessLoginRequest, PasswordlessLoginVerify

User = get_user_model()

logger = logging.getLogger(__name__)


@api_controller("/auth", tags=["Auth"])
class AuthController:
    @handle_exceptions
    @log_api_call()
    @http_post(
        "/passwordless/login/request", response={200: dict, 400: dict, 500: dict}
    )
    def request_passwordless_login(self, payload: PasswordlessLoginRequest):
        email = payload.email.lower()
        user_exists = User.objects.filter(email=email).exists()

        if user_exists:
            user = User.objects.get(email=email)
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(minutes=15)

            OneTimePassword.objects.create(
                user=user, token=token, expires_at=expires_at
            )

            magic_link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
            send_mail(
                "Your Magic Link",
                f"Click to login: {magic_link}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            return 200, {"detail": "If registered, you'll receive a magic link"}
        return 400, {"detail": "User does not exist"}

    @handle_exceptions
    @log_api_call()
    @http_post("/passwordless/login/verify", response={200: dict, 403: dict})
    def verify_passwordless_login(self, payload: PasswordlessLoginVerify):
        try:
            otp = OneTimePassword.objects.select_related("user").get(
                token=payload.token, is_used=False, expires_at__gte=datetime.now()
            )
        except OneTimePassword.DoesNotExist:
            return 403, {"detail": "Invalid or expired token"}

        otp.is_used = True
        otp.save()

        # Generate JWT tokens
        from django_ninja_jwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(otp.user)
        return 200, {"access": str(refresh.access_token), "refresh": str(refresh)}
