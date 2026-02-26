"""Declarative Todo controller — explicit try/except, no decorators.

This controller intentionally avoids custom decorators and instead uses
try/except blocks for every error case. It is the most verbose pattern
and mirrors how many Django REST Framework projects are written. It is
useful as a reference when you want full visibility into exactly what
happens at every step without any decorator magic.

Route prefix: /todos-declarative
"""

import logging

from django.db.models import Q
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import paginate
from ninja_jwt.authentication import JWTAuth

from todos.models import Todo
from todos.schemas import CreateTodoSchema, TodoSchema, UpdateTodoSchema

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


@api_controller(
    "/todos-declarative", tags=["Todos — Declarative (try/except)"], auth=JWTAuth()
)
class TodoControllerDeclarative:
    """Todo controller using explicit try/except blocks instead of decorators.

    Every method declares its own error handling so the control flow is
    completely transparent. This is the highest-verbosity, most declarative
    pattern and is ideal for developers who want to see exactly what is
    happening at every step without relying on decorator abstractions.
    """

    @paginate
    @http_get("/", response={200: list[TodoSchema], 400: dict, 500: dict})
    def list_todos(
        self,
        request,
        search: str | None = None,
        completed: bool | None = None,
        priority: str | None = None,
        ordering: str | None = None,
    ):
        """List todos with filtering, search, and pagination.

        Args:
            request: The HTTP request object containing the authenticated user.
            search: Case-insensitive substring search across title/description.
            completed: Filter by completion status when provided.
            priority: Filter by priority label (case-insensitive).
            ordering: Sort field (title, created_at, updated_at, priority; prefix with - for desc).

        Returns:
            Tuple of (200, queryset) on success or (500, error_dict) on failure.
        """
        try:
            queryset = Todo.objects.select_related("user").filter(user=request.user)

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

            return 200, queryset

        except Exception as exc:
            logger.exception("Failed to list todos for user %s", request.user.id)
            return 500, {
                "error": "Internal server error",
                "message": "Could not retrieve todos",
                "detail": str(exc),
            }

    @http_get("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    def get_todo(self, request, todo_id: str):
        """Retrieve a single todo by ID.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo.

        Returns:
            Tuple of (200, todo) on success, (404, error) if not found,
            or (500, error) on unexpected failure.
        """
        try:
            todo = Todo.objects.select_related("user").get(
                id=todo_id, user=request.user
            )
            return 200, todo
        except Todo.DoesNotExist:
            logger.warning("Todo %s not found for user %s", todo_id, request.user.id)
            return 404, {
                "error": "Not found",
                "message": f"Todo with id '{todo_id}' does not exist",
            }
        except Exception as exc:
            logger.exception("Failed to fetch todo %s", todo_id)
            return 500, {
                "error": "Internal server error",
                "message": "Could not retrieve todo",
                "detail": str(exc),
            }

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    def create_todo(self, request, payload: CreateTodoSchema):
        """Create a new todo for the authenticated user.

        Args:
            request: The HTTP request object.
            payload: Validated todo creation data.

        Returns:
            Tuple of (201, todo) on success, (400, error) on bad input,
            or (500, error) on unexpected failure.
        """
        try:
            if not payload.title or not payload.title.strip():
                return 400, {
                    "error": "Validation error",
                    "message": "Title is required and cannot be blank",
                }

            todo_data = payload.model_dump()
            todo_data["user"] = request.user
            todo = Todo.objects.create(**todo_data)

            logger.info(
                "Created todo '%s' (id=%s) for user %s",
                todo.title,
                todo.id,
                request.user.id,
            )

            return 201, todo

        except Exception as exc:
            logger.exception("Failed to create todo for user %s", request.user.id)
            return 500, {
                "error": "Internal server error",
                "message": "Could not create todo",
                "detail": str(exc),
            }

    @http_put("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    def update_todo(self, request, todo_id: str, payload: UpdateTodoSchema):
        """Apply partial updates to an existing todo.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo to update.
            payload: Validated update data (only provided fields are applied).

        Returns:
            Tuple of (200, todo) on success, (404, error) if not found,
            or (500, error) on unexpected failure.
        """
        try:
            todo = Todo.objects.get(id=todo_id, user=request.user)
        except Todo.DoesNotExist:
            return 404, {
                "error": "Not found",
                "message": f"Todo with id '{todo_id}' does not exist",
            }

        try:
            for attr, value in payload.model_dump(exclude_unset=True).items():
                setattr(todo, attr, value)
            todo.save()

            logger.info(
                "Updated todo '%s' (id=%s) for user %s",
                todo.title,
                todo.id,
                request.user.id,
            )

            return 200, todo

        except Exception as exc:
            logger.exception("Failed to update todo %s", todo_id)
            return 500, {
                "error": "Internal server error",
                "message": "Could not update todo",
                "detail": str(exc),
            }

    @http_delete("/{todo_id}", response={204: None, 404: dict, 500: dict})
    def delete_todo(self, request, todo_id: str):
        """Delete a todo owned by the authenticated user.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo to delete.

        Returns:
            Tuple of (204, None) on success, (404, error) if not found,
            or (500, error) on unexpected failure.
        """
        try:
            todo = Todo.objects.get(id=todo_id, user=request.user)
        except Todo.DoesNotExist:
            return 404, {
                "error": "Not found",
                "message": f"Todo with id '{todo_id}' does not exist",
            }

        try:
            todo.delete()
            logger.info("Deleted todo %s for user %s", todo_id, request.user.id)
            return 204, None
        except Exception as exc:
            logger.exception("Failed to delete todo %s", todo_id)
            return 500, {
                "error": "Internal server error",
                "message": "Could not delete todo",
                "detail": str(exc),
            }

    @paginate
    @http_get("/completed", response={200: list[TodoSchema], 500: dict})
    def list_completed_todos(self, request):
        """List completed todos for the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            Tuple of (200, queryset) on success or (500, error) on failure.
        """
        try:
            queryset = Todo.objects.filter(user=request.user, completed=True).order_by(
                "-updated_at"
            )
            return 200, queryset
        except Exception as exc:
            logger.exception(
                "Failed to list completed todos for user %s", request.user.id
            )
            return 500, {
                "error": "Internal server error",
                "message": "Could not retrieve completed todos",
                "detail": str(exc),
            }

    @paginate
    @http_get("/pending", response={200: list[TodoSchema], 500: dict})
    def list_pending_todos(self, request):
        """List pending (incomplete) todos for the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            Tuple of (200, queryset) on success or (500, error) on failure.
        """
        try:
            queryset = Todo.objects.filter(user=request.user, completed=False).order_by(
                "-created_at"
            )
            return 200, queryset
        except Exception as exc:
            logger.exception(
                "Failed to list pending todos for user %s", request.user.id
            )
            return 500, {
                "error": "Internal server error",
                "message": "Could not retrieve pending todos",
                "detail": str(exc),
            }

    @paginate
    @http_get("/search", response={200: list[TodoSchema], 500: dict})
    def search_todos(
        self,
        request,
        q: str | None = None,
        priority: str | None = None,
        completed: bool | None = None,
    ):
        """Advanced search across todo title and description.

        Args:
            request: The HTTP request object.
            q: Full-text search query across title and description.
            priority: Filter by priority label.
            completed: Filter by completion status.

        Returns:
            Tuple of (200, queryset) on success or (500, error) on failure.
        """
        try:
            queryset = Todo.objects.select_related("user").filter(user=request.user)

            if q:
                queryset = queryset.filter(
                    Q(title__icontains=q) | Q(description__icontains=q)
                )

            if priority:
                queryset = queryset.filter(priority__icontains=priority)

            if completed is not None:
                queryset = queryset.filter(completed=completed)

            return 200, queryset.order_by("-created_at")

        except Exception as exc:
            logger.exception("Search failed for user %s", request.user.id)
            return 500, {
                "error": "Internal server error",
                "message": "Search could not be completed",
                "detail": str(exc),
            }
