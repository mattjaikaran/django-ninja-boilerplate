"""Comprehensive database seeding command.

This command seeds the database with sample data for development and testing.
Based on patterns from larger production applications, it provides:
- Phased seeding (clear, create, verify)
- Configurable counts
- Progress reporting
- Transaction safety
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Seed the database with comprehensive sample data for development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=20,
            help="Number of users to create (default: 20)",
        )
        parser.add_argument(
            "--todos",
            type=int,
            default=50,
            help="Number of todos to create (default: 50)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help="Create comprehensive data with higher counts",
        )
        parser.add_argument(
            "--skip-users",
            action="store_true",
            help="Skip creating users (use existing)",
        )
        parser.add_argument(
            "--skip-todos",
            action="store_true",
            help="Skip creating todos",
        )
        parser.add_argument(
            "--superuser-only",
            action="store_true",
            help="Only create the superuser",
        )
        parser.add_argument(
            "--no-superuser",
            action="store_true",
            help="Skip creating superuser",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("🌱 STARTING DATABASE SEEDING"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        if options["clear"]:
            self.stdout.write(self.style.WARNING("🗑️  Clearing existing data..."))
            self.clear_data()
            self.stdout.write(self.style.SUCCESS("✅ Data cleared successfully\n"))

        # Adjust counts for full seeding
        if options["full"]:
            options["users"] = max(options["users"], 50)
            options["todos"] = max(options["todos"], 200)
            self.stdout.write(self.style.SUCCESS("📊 Full mode: Using higher counts\n"))

        # Phase 1: Create superuser
        if not options["no_superuser"]:
            self.stdout.write(self.style.SUCCESS("=== Phase 1: Superuser ==="))
            self.create_superuser()

        if options["superuser_only"]:
            self.print_summary(options)
            return

        # Phase 2: Create users
        users = []
        if not options["skip_users"]:
            self.stdout.write(self.style.SUCCESS("\n=== Phase 2: Users ==="))
            users = self.create_users(options["users"])
        else:
            users = list(User.objects.filter(is_superuser=False)[:50])
            self.stdout.write(f"📌 Using {len(users)} existing users\n")

        # Phase 3: Create todos
        if not options["skip_todos"] and users:
            self.stdout.write(self.style.SUCCESS("\n=== Phase 3: Todos ==="))
            self.create_todos(options["todos"], users)

        # Phase 4: Create OTP test data
        self.stdout.write(self.style.SUCCESS("\n=== Phase 4: OTP Test Data ==="))
        self.create_otp_test_data(users[:5] if users else [])

        # Print summary
        self.print_summary(options)

    def clear_data(self):
        """Clear existing data in correct order to respect FK constraints."""
        try:
            # Import models dynamically to avoid circular imports
            from core.models import OneTimePassword

            # Clear OTPs first
            OneTimePassword.objects.all().delete()
            self.stdout.write("   • Cleared OTPs")

            # Try to clear todos if the app exists
            try:
                from todos.models import Todo

                Todo.objects.all().delete()
                self.stdout.write("   • Cleared Todos")
            except ImportError:
                pass

            # Clear non-superuser accounts
            deleted, _ = User.objects.filter(is_superuser=False).delete()
            self.stdout.write(f"   • Cleared {deleted} users")

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Some data could not be cleared: {e}")
            )

    def create_superuser(self):
        """Create or verify superuser exists."""
        try:
            call_command("create_superuser")
            self.stdout.write(self.style.SUCCESS("✅ Superuser ready"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Superuser creation: {e}"))

    def create_users(self, count: int) -> list:
        """Create sample users with realistic data."""
        self.stdout.write(f"Creating {count} users...")

        users = []
        professions = [
            "Software Engineer",
            "Product Manager",
            "Designer",
            "Data Scientist",
            "DevOps Engineer",
            "Marketing Manager",
            "Sales Representative",
            "Customer Success",
            "HR Manager",
            "Finance Analyst",
        ]
        timezones = [
            "UTC",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Paris",
            "Asia/Tokyo",
            "Asia/Singapore",
            "Australia/Sydney",
        ]

        with transaction.atomic():
            for i in range(count):
                try:
                    first_name = fake.first_name()
                    last_name = fake.last_name()
                    username = f"{first_name.lower()}{last_name.lower()}{random.randint(1, 999)}"

                    user = User.objects.create_user(
                        email=f"{username}@example.com",
                        username=username,
                        password="password123",
                        first_name=first_name,
                        last_name=last_name,
                        bio=fake.paragraph(nb_sentences=2),
                        phone=fake.phone_number()[:20],
                        location=f"{fake.city()}, {fake.state_abbr()}",
                        website=fake.url() if random.choice([True, False]) else "",
                        timezone=random.choice(timezones),
                        is_verified=random.choice(
                            [True, True, True, False]
                        ),  # 75% verified
                        email_notifications=random.choice([True, True, False]),
                        push_notifications=random.choice([True, False]),
                        metadata={
                            "profession": random.choice(professions),
                            "signup_source": random.choice(
                                ["organic", "referral", "ads", "social"]
                            ),
                        },
                    )
                    users.append(user)

                    if (i + 1) % 10 == 0:
                        self.stdout.write(f"   • Created {i + 1}/{count} users")

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"   ⚠️  User {i + 1}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Created {len(users)} users"))
        return users

    def create_todos(self, count: int, users: list):
        """Create sample todos for users."""
        try:
            from todos.models import Todo

            self.stdout.write(f"Creating {count} todos...")

            todos_created = 0
            priorities = ["low", "medium", "high"]
            categories = [
                "Work",
                "Personal",
                "Shopping",
                "Health",
                "Learning",
                "Finance",
                "Home",
                "Social",
            ]

            with transaction.atomic():
                for i in range(count):
                    try:
                        user = random.choice(users)
                        is_completed = random.choice([True, True, False, False, False])

                        Todo.objects.create(
                            user=user,
                            title=fake.sentence(nb_words=random.randint(3, 8))[:-1],
                            description=fake.paragraph(
                                nb_sentences=random.randint(1, 3)
                            )
                            if random.choice([True, False])
                            else "",
                            priority=random.choice(priorities),
                            is_completed=is_completed,
                            due_date=timezone.now().date()
                            + timedelta(days=random.randint(-7, 30))
                            if random.choice([True, True, False])
                            else None,
                            metadata={
                                "category": random.choice(categories),
                                "estimated_minutes": random.choice(
                                    [15, 30, 60, 120, 240]
                                ),
                            },
                        )
                        todos_created += 1

                        if (i + 1) % 25 == 0:
                            self.stdout.write(f"   • Created {i + 1}/{count} todos")

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"   ⚠️  Todo {i + 1}: {e}")
                        )

            self.stdout.write(self.style.SUCCESS(f"✅ Created {todos_created} todos"))

        except ImportError:
            self.stdout.write(
                self.style.WARNING("⚠️  Todos app not found, skipping todos creation")
            )

    def create_otp_test_data(self, users: list):
        """Create sample OTP data for testing."""
        from core.models import OneTimePassword, OTPDeliveryMethod, OTPPurpose

        if not users:
            self.stdout.write("   • No users for OTP data, skipping")
            return

        self.stdout.write("Creating OTP test data...")

        otps_created = 0
        purposes = [p.value for p in OTPPurpose]
        methods = [m.value for m in OTPDeliveryMethod]

        with transaction.atomic():
            for user in users:
                try:
                    # Create a few OTPs per user
                    for _ in range(random.randint(1, 3)):
                        purpose = random.choice(purposes)
                        method = random.choice(methods)

                        # Some expired, some valid
                        if random.choice([True, False]):
                            expires_at = timezone.now() + timedelta(minutes=10)
                            is_used = False
                        else:
                            expires_at = timezone.now() - timedelta(hours=1)
                            is_used = True

                        OneTimePassword.objects.create(
                            user=user,
                            code=OneTimePassword.generate_code(),
                            token=OneTimePassword.generate_token(),
                            purpose=purpose,
                            delivery_method=method,
                            expires_at=expires_at,
                            is_used=is_used,
                            attempts=random.randint(0, 3),
                            ip_address="127.0.0.1",
                            user_agent="Seed Script",
                        )
                        otps_created += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"   ⚠️  OTP for {user.email}: {e}")
                    )

        self.stdout.write(self.style.SUCCESS(f"✅ Created {otps_created} OTP records"))

    def print_summary(self, options):
        """Print seeding summary."""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("🎉 DATABASE SEEDING COMPLETE!"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

        self.stdout.write(self.style.SUCCESS("\n📊 Data Summary:"))

        # Count records
        user_count = User.objects.count()
        self.stdout.write(f"   • Users: {user_count}")

        try:
            from todos.models import Todo

            todo_count = Todo.objects.count()
            completed = Todo.objects.filter(is_completed=True).count()
            self.stdout.write(f"   • Todos: {todo_count} ({completed} completed)")
        except ImportError:
            pass

        try:
            from core.models import OneTimePassword

            otp_count = OneTimePassword.objects.count()
            self.stdout.write(f"   • OTP Records: {otp_count}")
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("\n🔑 Default Credentials:"))
        self.stdout.write("   • Superuser: admin@example.com / password123")
        self.stdout.write("   • Test users: *@example.com / password123")

        self.stdout.write(self.style.SUCCESS("\n🚀 Ready for Development:"))
        self.stdout.write("   • Admin: http://localhost:8000/admin")
        self.stdout.write("   • API Docs: http://localhost:8000/api/docs")

        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))
