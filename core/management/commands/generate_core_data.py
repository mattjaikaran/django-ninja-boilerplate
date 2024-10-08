from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker

User = get_user_model()


class Command(BaseCommand):
    help = "Generate test data for the core app"

    def add_arguments(self, parser):
        parser.add_argument("--model", type=str, help="Model to generate data for")
        parser.add_argument("--count", type=int, help="Number of objects to create")

    def handle(self, *args, **options):
        model = options["model"]
        count = options["count"]
        fake = Faker()

        if model == "User":
            self.generate_users(count, fake)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown model: {model}"))

    def generate_users(self, count, fake):
        for _ in range(count):
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f"{first_name.lower()}{last_name.lower()}"
            email = f"{username}@example.com"

            User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=username,
                password="Test1234!",
            )
        self.stdout.write(self.style.SUCCESS(f"Created {count} users"))
