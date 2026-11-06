from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from api.settings.common import env

# Passwords published in this repository's templates and scripts.
_PUBLISHED_PASSWORDS = {
    "Password123!",
    "admin123",
    "admin",
    "password",
    "changeme",
    "CHANGE_ME",
}
_MIN_PASSWORD_LENGTH = 12
_REQUIRED_VARIABLES = (
    "SUPERUSER_EMAIL",
    "SUPERUSER_USERNAME",
    "SUPERUSER_PASSWORD",
    "SUPERUSER_FIRST_NAME",
    "SUPERUSER_LAST_NAME",
)


class Command(BaseCommand):
    help = "Creates a superuser from environment variables"

    def handle(self, *args, **options):
        User = get_user_model()

        # An explicit empty default lets the check below name every missing
        # variable instead of django-environ raising on the first unset one.
        values = {name: env(name, default="") for name in _REQUIRED_VARIABLES}
        missing = [name for name, value in values.items() if not value.strip()]
        if missing:
            raise CommandError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        email = values["SUPERUSER_EMAIL"].strip()
        username = values["SUPERUSER_USERNAME"].strip()
        password = values["SUPERUSER_PASSWORD"]
        login_field = User.USERNAME_FIELD

        # Outside development, refuse a published or short password. The
        # container entrypoint applies the same rule before calling this.
        if env("ENVIRONMENT", default="development") != "development" and (
            password in _PUBLISHED_PASSWORDS or len(password) < _MIN_PASSWORD_LENGTH
        ):
            raise CommandError(
                "SUPERUSER_PASSWORD is a published default or shorter than "
                f"{_MIN_PASSWORD_LENGTH} characters."
            )

        # Idempotent: `just setup` and the single-image entrypoint both call
        # this, so a re-run must not report a failure. The user model logs in
        # by email (USERNAME_FIELD), so email is the existence key.
        if User.objects.filter(email=email.lower()).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser '{email}' already exists. "
                    f"Log in with {login_field}: {email}"
                )
            )
            return

        try:
            User.objects.create_superuser(
                email=email,
                username=username,
                password=password,
                first_name=values["SUPERUSER_FIRST_NAME"],
                last_name=values["SUPERUSER_LAST_NAME"],
            )
        except ValidationError as e:
            raise CommandError(f"Could not create superuser: {e}") from e

        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser '{email}' created successfully. "
                f"Log in with {login_field}: {email}"
            )
        )
