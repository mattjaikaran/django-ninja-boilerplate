"""Data access for the Todo app.

The repository owns every ORM query for ``Todo``. The service owns the
business rules (validation, 404 mapping, logging) and calls these methods.
"""

from typing import Any

from django.db.models import Q, QuerySet

from todos.models import Todo


class TodoRepository:
    """Query and persistence operations for the Todo model."""

    def get_user_queryset(self, user: Any) -> QuerySet:
        """Return todos belonging to *user* with their owner preloaded."""
        return Todo.objects.select_related("user").filter(user=user)

    def get_by_id_and_user(self, todo_id: str, user: Any) -> Todo | None:
        """Return the todo with *todo_id* owned by *user*, or None."""
        return self.get_user_queryset(user).filter(id=todo_id).first()

    def create(self, data: dict[str, Any]) -> Todo:
        """Create a todo from *data*."""
        return Todo.objects.create(**data)

    def update(self, todo: Todo, data: dict[str, Any]) -> Todo:
        """Apply *data* to *todo* and save it."""
        for attr, value in data.items():
            setattr(todo, attr, value)
        todo.save()
        return todo

    def delete(self, todo: Todo) -> None:
        """Delete *todo*."""
        todo.delete()

    def completed(self, user: Any) -> QuerySet:
        """Return completed todos for *user*, most recently updated first."""
        return Todo.objects.filter(user=user, completed=True).order_by("-updated_at")

    def pending(self, user: Any) -> QuerySet:
        """Return incomplete todos for *user*, most recently created first."""
        return Todo.objects.filter(user=user, completed=False).order_by("-created_at")

    def search(
        self,
        user: Any,
        q: str | None = None,
        priority: str | None = None,
        completed: bool | None = None,
    ) -> QuerySet:
        """Return *user*'s todos matching the search filters, newest first."""
        queryset = self.get_user_queryset(user)

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(description__icontains=q)
            )

        if priority:
            queryset = queryset.filter(priority__icontains=priority)

        if completed is not None:
            queryset = queryset.filter(completed=completed)

        return queryset.order_by("-created_at")
