from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

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


class Command(BaseCommand):
    help = "Creates a superuser from environment variables"

    def handle(self, *args, **options):
        # Get the User model
        User = get_user_model()

        # Get superuser details from environment variables
        email = env("SUPERUSER_EMAIL")
        username = env("SUPERUSER_USERNAME")
        password = env("SUPERUSER_PASSWORD")
        first_name = env("SUPERUSER_FIRST_NAME")
        last_name = env("SUPERUSER_LAST_NAME")

        # Check if all required fields are provided
        if not all([email, username, password, first_name, last_name]):
            self.stdout.write(
                self.style.ERROR(
                    "Error: All superuser fields must be provided in the .env file."
                )
            )
            return

        # Outside development, refuse a published or short password. The
        # container entrypoint applies the same rule before calling this.
        if env("ENVIRONMENT", default="development") != "development" and (
            password in _PUBLISHED_PASSWORDS or len(password) < _MIN_PASSWORD_LENGTH
        ):
            self.stdout.write(
                self.style.ERROR(
                    "Error: SUPERUSER_PASSWORD is a published default or shorter "
                    f"than {_MIN_PASSWORD_LENGTH} characters."
                )
            )
            return

        # Idempotent: `just setup` and the single-image entrypoint both call
        # this, so a re-run must not report a failure.
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f"Superuser '{username}' already exists.")
            )
            return

        try:
            # Create the superuser
            superuser = User.objects.create_superuser(
                email=email,
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            print(superuser)
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created successfully.")
            )
        except ValidationError as e:
            self.stdout.write(self.style.ERROR(f"Error creating superuser: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
