# Generated manually for APIKey model

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_audit_log"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="APIKey",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                (
                    "prefix",
                    models.CharField(
                        db_index=True, editable=False, max_length=8, unique=True
                    ),
                ),
                (
                    "hashed_key",
                    models.CharField(editable=False, max_length=128),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Human-readable label for this key",
                        max_length=255,
                    ),
                ),
                (
                    "scopes",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text='Granular permissions, e.g. ["read:todos", "write:todos"]',
                    ),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "revoked",
                    models.BooleanField(db_index=True, default=False),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "API Key",
                "verbose_name_plural": "API Keys",
                "db_table": "core_api_key",
                "ordering": ["-created_at"],
            },
        ),
    ]
