import logging

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from api.search_filters import TodoSearchFilter, get_todo_search_engine
from todos.models import Todo
from todos.schemas import CreateTodoSchema, TodoSchema, UpdateTodoSchema

logger = logging.getLogger(__name__)


@api_controller("/todos", tags=["Todos"])
class TodoController:
    @list_endpoint(
        cache_timeout=300,
        select_related=["user"],
        search_fields=["title", "description"],
        filter_fields={
            "completed": "boolean",
            "priority": "icontains",
        },
        ordering_fields=["title", "created_at", "updated_at", "priority"],
    )
    @http_get("/all", response={200: list[TodoSchema]})
    def list_all_todos(self, request, filters: TodoSearchFilter = None):  # noqa: ARG002
        """List all todos with search, filtering, and pagination."""
        queryset = Todo.objects.all()

        if filters:
            search_engine = get_todo_search_engine()
            queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @list_endpoint(
        cache_timeout=300,
        select_related=["user"],
        search_fields=["title", "description"],
        filter_fields={
            "completed": "boolean",
            "priority": "icontains",
        },
        ordering_fields=["title", "created_at", "updated_at", "priority"],
    )
    @http_get("/", response={200: list[TodoSchema]})
    def list_user_todos(self, request, filters: TodoSearchFilter = None):
        """List todos for authenticated user with search, filtering, and pagination."""
        user = request.user
        queryset = Todo.objects.filter(user=user)

        if filters:
            search_engine = get_todo_search_engine()
            queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @create_endpoint()
    @http_post("/", response={201: TodoSchema})
    def create_todo(self, request, payload: CreateTodoSchema):
        """Create a new todo for the authenticated user."""
        user = request.user
        todo = Todo.objects.create(user=user, **payload.dict())
        return 201, todo

    @detail_endpoint(select_related=["user"])
    @http_get("/{str:todo_id}", response={200: TodoSchema, 404: dict})
    def get_todo(self, request, todo_id: str):
        """Get a specific todo by ID for the authenticated user."""
        user = request.user
        todo = get_object_or_404(Todo, id=todo_id, user=user)
        return 200, todo

    @update_endpoint(select_related=["user"])
    @http_put("/{str:todo_id}", response={200: TodoSchema, 404: dict})
    def update_todo(self, request, todo_id: str, payload: UpdateTodoSchema):
        """Update a specific todo by ID for the authenticated user."""
        user = request.user
        todo = get_object_or_404(Todo, id=todo_id, user=user)

        # Apply updates
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(todo, key, value)
        todo.save()

        return 200, todo

    @delete_endpoint()
    @http_delete("/{str:todo_id}", response={204: dict, 404: dict})
    def delete_todo(self, request, todo_id: str):
        """Delete a specific todo by ID for the authenticated user."""
        user = request.user
        todo = get_object_or_404(Todo, id=todo_id, user=user)
        todo.delete()
        return 204, {"message": "Todo deleted successfully"}

    @list_endpoint(
        cache_timeout=300,
        select_related=["user"],
        search_fields=["title", "description"],
        filter_fields={
            "completed": "boolean",
            "priority": "icontains",
        },
        ordering_fields=["title", "created_at", "updated_at", "priority"],
    )
    @http_get("/search", response={200: list[TodoSchema]})
    def search_todos(self, request, filters: TodoSearchFilter):
        """Advanced search endpoint for todos."""
        user = request.user
        queryset = Todo.objects.filter(user=user)

        search_engine = get_todo_search_engine()
        queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @list_endpoint(
        cache_timeout=300,
        select_related=["user"],
    )
    @http_get("/completed", response={200: list[TodoSchema]})
    def list_completed_todos(self, request):
        """List completed todos for authenticated user."""
        user = request.user
        queryset = Todo.objects.filter(user=user, completed=True).order_by(
            "-updated_at"
        )
        return 200, queryset

    @list_endpoint(
        cache_timeout=300,
        select_related=["user"],
    )
    @http_get("/pending", response={200: list[TodoSchema]})
    def list_pending_todos(self, request):
        """List pending (incomplete) todos for authenticated user."""
        user = request.user
        queryset = Todo.objects.filter(user=user, completed=False).order_by(
            "-created_at"
        )
        return 200, queryset
