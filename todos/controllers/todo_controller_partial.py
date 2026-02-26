"""Partial decorator Todo controller — selective use of custom decorators.

This controller applies ``handle_exceptions`` and ``log_api_call`` only
where they add the most value: mutating operations (POST/PUT/DELETE).
Read endpoints are left undecorated to show that you can mix and match
rather than applying decorators uniformly across all methods.

Route prefix: /todos-partial
"""

import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import paginate
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call
from todos.models import Todo
from todos.schemas import CreateTodoSchema, TodoSchema, UpdateTodoSchema

logger = logging.getLogger(__name__)


@api_controller(
    "/todos-partial",
    tags=["Todos — Partial (selective decorators)"],
    auth=JWTAuth(),
)
class TodoControllerPartial:
    """Todo controller demonstrating selective decorator usage.

    Read endpoints (GET) are kept plain — they rely on Django Ninja to
    surface errors naturally. Write endpoints (POST/PUT/DELETE) use
    ``handle_exceptions`` for structured error responses and
    ``log_api_call`` for observability. This is a practical middle ground
    between zero-decorator and full-decorator patterns.
    """

    # ------------------------------------------------------------------
    # Read endpoints — no custom decorators
    # ------------------------------------------------------------------

    @paginate
    @http_get("/", response={200: list[TodoSchema]})
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
            search: Case-insensitive search across title and description.
            completed: Filter by completion status.
            priority: Filter by priority label.
            ordering: Sort field (title, created_at, updated_at, priority;
                prefix with ``-`` for descending order).

        Returns:
            QuerySet of todos belonging to the authenticated user.
        """
        queryset = Todo.objects.select_related("user").filter(user=request.user)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        if completed is not None:
            queryset = queryset.filter(completed=completed)

        if priority:
            queryset = queryset.filter(priority__icontains=priority)

        valid_orderings = [
            "title",
            "-title",
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
            "priority",
            "-priority",
        ]
        if ordering and ordering in valid_orderings:
            queryset = queryset.order_by(ordering)

        return queryset

    @http_get("/{todo_id}", response={200: TodoSchema, 404: dict})
    def get_todo(self, request, todo_id: str):
        """Retrieve a single todo by ID.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo.

        Returns:
            The matching Todo instance, or 404 if not found.
        """
        return get_object_or_404(
            Todo.objects.select_related("user"), id=todo_id, user=request.user
        )

    @paginate
    @http_get("/completed", response={200: list[TodoSchema]})
    def list_completed_todos(self, request):
        """List completed todos for the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            QuerySet of completed Todo objects.
        """
        return Todo.objects.filter(user=request.user, completed=True).order_by(
            "-updated_at"
        )

    @paginate
    @http_get("/pending", response={200: list[TodoSchema]})
    def list_pending_todos(self, request):
        """List pending (incomplete) todos for the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            QuerySet of incomplete Todo objects.
        """
        return Todo.objects.filter(user=request.user, completed=False).order_by(
            "-created_at"
        )

    @paginate
    @http_get("/search", response={200: list[TodoSchema]})
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
            q: Full-text search query.
            priority: Filter by priority label.
            completed: Filter by completion status.

        Returns:
            QuerySet of matching todos ordered by newest first.
        """
        queryset = Todo.objects.select_related("user").filter(user=request.user)

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(description__icontains=q)
            )

        if priority:
            queryset = queryset.filter(priority__icontains=priority)

        if completed is not None:
            queryset = queryset.filter(completed=completed)

        return queryset.order_by("-created_at")

    # ------------------------------------------------------------------
    # Write endpoints — decorated for error handling + observability
    # ------------------------------------------------------------------

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    def create_todo(self, request, payload: CreateTodoSchema):
        """Create a new todo for the authenticated user.

        Decorated with ``log_api_call`` for audit visibility and
        ``handle_exceptions`` so any DB or validation error returns a
        structured 500 response instead of an unhandled exception.

        Args:
            request: The HTTP request object.
            payload: Validated todo creation data.

        Returns:
            Tuple of (201, todo) on success.
        """
        todo_data = payload.model_dump()
        todo_data["user"] = request.user
        todo = Todo.objects.create(**todo_data)
        logger.info("Created todo '%s' (id=%s)", todo.title, todo.id)
        return 201, todo

    @http_put("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    @log_api_call(include_payload=True)
    @handle_exceptions()
    def update_todo(self, request, todo_id: str, payload: UpdateTodoSchema):
        """Apply partial updates to an existing todo.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo to update.
            payload: Validated update data; only provided fields are applied.

        Returns:
            Tuple of (200, todo) on success.
        """
        todo = get_object_or_404(Todo, id=todo_id, user=request.user)

        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(todo, attr, value)
        todo.save()

        return 200, todo

    @http_delete("/{todo_id}", response={204: None, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_todo(self, request, todo_id: str):
        """Delete a todo owned by the authenticated user.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo to delete.

        Returns:
            Tuple of (204, None) on success.
        """
        todo = get_object_or_404(Todo, id=todo_id, user=request.user)
        todo.delete()
        return 204, None
