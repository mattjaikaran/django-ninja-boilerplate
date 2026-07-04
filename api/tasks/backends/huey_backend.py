"""Huey backend configuration.

Install: uv add huey
Set: TASK_BACKEND=huey

Huey is a lightweight task queue with Redis, SQLite, or in-memory backends.
In DEBUG mode, tasks run synchronously by default (immediate=True).

Worker: python manage.py run_huey
"""
