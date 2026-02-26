"""Primary Todo controller — full decorators + service layer.

This is the most structured pattern in the boilerplate. Controllers are
thin: they only handle HTTP concerns (auth, status codes, request/response
binding). All business logic lives in ``TodoService``, which is injected
via ``__init__`` so it is trivial to swap out or mock in tests.

Route prefix: /todos
"""

import logging

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import paginate
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call, validate_request
from todos.schemas import CreateTodoSchema, TodoSchema, UpdateTodoSchema
from todos.services import TodoService

logger = logging.getLogger(__name__)


@api_controller("/todos", tags=["Todos"], auth=JWTAuth())
class TodoController:
    """Todo controller using full decorator stack and an injected service.

    The ``TodoService`` instance is created once in ``__init__`` and reused
    across all requests. Controller methods are intentionally thin — they
    delegate to the service and return the appropriate HTTP status code.
    """

    def __init__(self):
        """Initialise the controller with an injected TodoService."""
        self.service = TodoService()

    # ------------------------------------------------------------------
    # List / search
    # ------------------------------------------------------------------

    @paginate
    @http_get("/", response={200: list[TodoSchema], 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_todos(
        self,
        request,
        search: str | None = None,
        completed: bool | None = None,
        priority: str | None = None,
        ordering: str | None = None,
    ):
        """List todos with advanced filtering, search, and pagination.

        Args:
            request: The HTTP request object containing the authenticated user.
            search: Case-insensitive search across title and description.
            completed: Filter by completion status.
            priority: Filter by priority label.
            ordering: Sort field (title, created_at, updated_at, priority;
                prefix with ``-`` for descending order).

        Returns:
            Tuple of (200, queryset) containing filtered todos.
        """
        return 200, self.service.list_todos(
            user=request.user,
            search=search,
            completed=completed,
            priority=priority,
            ordering=ordering,
        )

    @http_get("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def get_todo(self, request, todo_id: str):
        """Retrieve a single todo by ID.

        Args:
            request: The HTTP request object.
            todo_id: The UUID primary key of the todo.

        Returns:
            Tuple of (200, todo) on success.
        """
        return 200, self.service.get_todo(todo_id, request.user)

    @paginate
    @http_get("/completed", response={200: list[TodoSchema], 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_completed_todos(self, request):
        """List completed todos for the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            Tuple of (200, queryset) of completed todos.
        """
        return 200, self.service.list_completed_todos(request.user)

    @paginate
    @http_get("/pending", response={200: list[TodoSchema], 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_pending_todos(self, request):
        """List pending (incomplete) todos for the authenticated user.

        Args:
            request: The HTTP request object.

        Returns:
            Tuple of (200, queryset) of pending todos.
        """
        return 200, self.service.list_pending_todos(request.user)

    @paginate
    @http_get("/search", response={200: list[TodoSchema], 500: dict})
    @handle_exceptions()
    @log_api_call()
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
            Tuple of (200, queryset) of matching todos.
        """
        return 200, self.service.search_todos(
            user=request.user,
            q=q,
            priority=priority,
            completed=completed,
        )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_todo(self, request, payload: CreateTodoSchema):
        """Create a new todo for the authenticated user.

        Args:
            request: The HTTP request object.
            payload: Validated todo creation data.

        Returns:
            Tuple of (201, todo) for the created instance.
        """
        return 201, self.service.create_todo(payload, request.user)

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
        return 200, self.service.update_todo(todo_id, payload, request.user)

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
        self.service.delete_todo(todo_id, request.user)
        return 204, None
