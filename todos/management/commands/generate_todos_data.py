from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker
from todos.models import Todo
import random

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate sample todo data for testing and development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--todos",
            type=int,
            default=10,
            help="The number of todos to create (default: 10)",
        )
        parser.add_argument(
            "--user",
            type=str,
            help="Username or email of the user to create todos for (optional)",
        )

    def handle(self, *args, **options):
        num_todos = options["todos"]
        user_identifier = options.get("user")

        # Get or create user
        if user_identifier:
            try:
                user = User.objects.get(username=user_identifier) or User.objects.get(
                    email=user_identifier
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Creating todos for existing user: {user.username}"
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"User with identifier {user_identifier} not found"
                    )
                )
                return
        else:
            # Get a random user or create one if none exist
            if not User.objects.exists():
                user = User.objects.create_user(
                    username=fake.user_name(),
                    email=fake.email(),
                    password="password123",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created new user: {user.username}")
                )
            else:
                user = User.objects.order_by("?").first()
                self.stdout.write(
                    self.style.SUCCESS(f"Using existing user: {user.username}")
                )

        # Generate todos
        todos_created = 0
        for _ in range(num_todos):
            todo = Todo.objects.create(
                user=user,
                title=fake.sentence(nb_words=4)[:-1],  # Remove trailing period
                description=fake.paragraph(nb_sentences=3),
                completed=random.choice([True, False]),
            )
            todos_created += 1
            self.stdout.write(self.style.SUCCESS(f"Created todo: {todo.title}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully created {todos_created} todos for user {user.username}"
            )
        )
