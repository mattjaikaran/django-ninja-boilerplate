"""Codebase Atlas — interactive architecture map for the running project.

The atlas scans the installed local apps, counts lines of code, reads models
and API routes from the live OpenAPI schema, then renders an isometric city
map in the admin panel. Run ``python manage.py atlas`` to regenerate the
data file, or use the Regenerate button on the admin page.
"""

__all__ = ["apps"]
