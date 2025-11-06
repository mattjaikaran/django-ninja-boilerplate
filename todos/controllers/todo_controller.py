import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import paginate

from api.decorators import handle_exceptions, log_api_call, validate_request
from todos.models import Todo
from todos.schemas import CreateTodoSchema, TodoSchema, UpdateTodoSchema

logger = logging.getLogger(__name__)


@api_controller("/todos", tags=["Todos"])
class TodoController:
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
        """List todos with advanced filtering, search and pagination.

        Returns:
            list[TodoSchema]: List of todos

        Args:
            search: Search in title, description
            completed: Filter by completion status
            priority: Filter by priority level
            ordering: Order by field (title, created_at, updated_at, priority, -title, -created_at, -updated_at, -priority)
        """
        queryset = Todo.objects.select_related("user").filter(user=request.user)

        # Apply search filter
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        # Apply filters
        if completed is not None:
            queryset = queryset.filter(completed=completed)

        if priority:
            queryset = queryset.filter(priority__icontains=priority)

        # Apply ordering
        if ordering:
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
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)

        return 200, queryset

    @http_get("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def get_todo(self, request, todo_id: str):
        """Get a specific todo by ID for the authenticated user."""
        return 200, get_object_or_404(
            Todo.objects.select_related("user"), id=todo_id, user=request.user
        )

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_todo(self, request, payload: CreateTodoSchema):
        """Create a new todo for the authenticated user."""
        todo_data = payload.model_dump()
        todo_data["user"] = request.user
        todo = Todo.objects.create(**todo_data)

        logger.info(f"Successfully created todo: {todo.title} (ID: {todo.id})")

        return 201, todo

    @http_put("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    @log_api_call(include_payload=True)
    @handle_exceptions()
    def update_todo(self, request, todo_id: str, payload: UpdateTodoSchema):
        """Update an existing todo for the authenticated user."""
        todo = get_object_or_404(Todo, id=todo_id, user=request.user)

        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(todo, attr, value)
        todo.save()

        return 200, todo

    @http_delete("/{todo_id}", response={204: None, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_todo(self, request, todo_id: str):
        """Delete a todo for the authenticated user."""
        todo = get_object_or_404(Todo, id=todo_id, user=request.user)
        todo.delete()
        return 204, None

    @paginate
    @http_get("/completed", response={200: list[TodoSchema], 400: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_completed_todos(self, request):
        """List completed todos for authenticated user."""
        queryset = Todo.objects.filter(user=request.user, completed=True).order_by(
            "-updated_at"
        )
        return 200, queryset

    @paginate
    @http_get("/pending", response={200: list[TodoSchema], 400: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_pending_todos(self, request):
        """List pending (incomplete) todos for authenticated user."""
        queryset = Todo.objects.filter(user=request.user, completed=False).order_by(
            "-created_at"
        )
        return 200, queryset

    @paginate
    @http_get("/search", response={200: list[TodoSchema], 400: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def search_todos(
        self,
        request,
        q: str | None = None,
        priority: str | None = None,
        completed: bool | None = None,
    ):
        """Advanced search for todos."""
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
