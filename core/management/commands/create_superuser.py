from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from api.settings import env


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

        try:
            # Create the superuser
            superuser = User.objects.create_superuser(
                email=email,
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created successfully.")
            )
        except ValidationError as e:
            self.stdout.write(self.style.ERROR(f"Error creating superuser: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
