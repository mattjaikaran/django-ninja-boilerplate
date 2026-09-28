"""Resize fixture embeddings to 1024 dimensions for Qwen3-Embedding-0.6B.

Vectors from the old 1536-dimension column cannot be cast to 1024, and they
came from a different model, so the migration clears them first. Rebuild
them with ``python manage.py embed_decisions``.
"""

import pgvector.django.vector
from django.db import migrations


def clear_embeddings(apps, schema_editor):
    """Drop vectors of the old width; they are recomputed after the migration."""
    DecisionFixture = apps.get_model("decisions", "DecisionFixture")
    DecisionFixture.objects.exclude(embedding=None).update(embedding=None)


class Migration(migrations.Migration):
    dependencies = [
        ("decisions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_embeddings, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="decisionfixture",
            name="embedding",
            field=pgvector.django.vector.VectorField(
                blank=True, dimensions=1024, null=True
            ),
        ),
    ]
