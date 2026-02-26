"""Business logic for the Todo app.

This service layer extracts all database operations and business rules
from the controller, keeping controllers thin and logic testable.
"""

import logging
from typing import Any

from django.db.models import Q, QuerySet
from django.http import Http404

from todos.models import Todo
from todos.schemas import CreateTodoSchema, UpdateTodoSchema

logger = logging.getLogger(__name__)

VALID_ORDERINGS = [
    "title",
    "-title",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
    "priority",
    "-priority",
]


class TodoService:
    """Service class encapsulating all Todo business logic.

    Handles CRUD operations, filtering, search, and ordering.
    All methods raise Http404 when a resource is not found so controllers
    can rely on ``handle_exceptions`` to map that to a 404 response.
    """

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_user_todos(self, user: Any) -> QuerySet:
        """Return all todos belonging to *user*.

        Args:
            user: The authenticated user instance.

        Returns:
            QuerySet of Todo objects owned by the user.
        """
        return Todo.objects.select_related("user").filter(user=user)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_todos(
        self,
        user: Any,
        search: str | None = None,
        completed: bool | None = None,
        priority: str | None = None,
        ordering: str | None = None,
    ) -> QuerySet:
        """Return a filtered, ordered queryset of todos for *user*.

        Args:
            user: The authenticated user instance.
            search: Case-insensitive substring search across title/description.
            completed: Filter by completion status when provided.
            priority: Filter by priority label (case-insensitive).
            ordering: Sort field. Accepted values: title, created_at,
                updated_at, priority (prefix with - for descending).

        Returns:
            Filtered QuerySet of Todo objects.
        """
        queryset = self.get_user_todos(user)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        if completed is not None:
            queryset = queryset.filter(completed=completed)

        if priority:
            queryset = queryset.filter(priority__icontains=priority)

        if ordering and ordering in VALID_ORDERINGS:
            queryset = queryset.order_by(ordering)

        return queryset

    def get_todo(self, todo_id: str, user: Any) -> Todo:
        """Fetch a single todo owned by *user*.

        Args:
            todo_id: Primary key of the Todo.
            user: The authenticated user instance.

        Returns:
            The matching Todo instance.

        Raises:
            Http404: If the todo does not exist or belongs to another user.
        """
        try:
            return Todo.objects.select_related("user").get(id=todo_id, user=user)
        except Todo.DoesNotExist as err:
            raise Http404(f"Todo {todo_id} not found") from err

    def create_todo(self, payload: CreateTodoSchema, user: Any) -> Todo:
        """Create a new todo for *user*.

        Args:
            payload: Validated creation schema.
            user: The authenticated user instance.

        Returns:
            The newly created Todo instance.
        """
        todo_data = payload.model_dump()
        todo_data["user"] = user
        todo = Todo.objects.create(**todo_data)
        logger.info("Created todo: %s (id=%s)", todo.title, todo.id)
        return todo

    def update_todo(self, todo_id: str, payload: UpdateTodoSchema, user: Any) -> Todo:
        """Apply partial updates to an existing todo.

        Args:
            todo_id: Primary key of the Todo to update.
            payload: Validated update schema (only provided fields are applied).
            user: The authenticated user instance.

        Returns:
            The updated Todo instance.

        Raises:
            Http404: If the todo does not exist or belongs to another user.
        """
        todo = self.get_todo(todo_id, user)
        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(todo, attr, value)
        todo.save()
        logger.info("Updated todo: %s (id=%s)", todo.title, todo.id)
        return todo

    def delete_todo(self, todo_id: str, user: Any) -> None:
        """Delete a todo owned by *user*.

        Args:
            todo_id: Primary key of the Todo to delete.
            user: The authenticated user instance.

        Raises:
            Http404: If the todo does not exist or belongs to another user.
        """
        todo = self.get_todo(todo_id, user)
        logger.info("Deleting todo: %s (id=%s)", todo.title, todo.id)
        todo.delete()

    # ------------------------------------------------------------------
    # Filtered list helpers
    # ------------------------------------------------------------------

    def list_completed_todos(self, user: Any) -> QuerySet:
        """Return completed todos for *user* ordered by most recently updated.

        Args:
            user: The authenticated user instance.

        Returns:
            QuerySet of completed Todo objects.
        """
        return Todo.objects.filter(user=user, completed=True).order_by("-updated_at")

    def list_pending_todos(self, user: Any) -> QuerySet:
        """Return incomplete todos for *user* ordered by most recently created.

        Args:
            user: The authenticated user instance.

        Returns:
            QuerySet of pending Todo objects.
        """
        return Todo.objects.filter(user=user, completed=False).order_by("-created_at")

    def search_todos(
        self,
        user: Any,
        q: str | None = None,
        priority: str | None = None,
        completed: bool | None = None,
    ) -> QuerySet:
        """Advanced search across todo fields.

        Args:
            user: The authenticated user instance.
            q: Full-text search query across title and description.
            priority: Filter by priority label.
            completed: Filter by completion status.

        Returns:
            QuerySet of matching Todo objects ordered by newest first.
        """
        queryset = self.get_user_todos(user)

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(description__icontains=q)
            )

        if priority:
            queryset = queryset.filter(priority__icontains=priority)

        if completed is not None:
            queryset = queryset.filter(completed=completed)

        return queryset.order_by("-created_at")
