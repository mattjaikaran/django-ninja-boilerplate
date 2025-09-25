import logging

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from todos.models import Todo
from todos.schemas import CreateTodoSchema, TodoSchema, UpdateTodoSchema

logger = logging.getLogger(__name__)


@api_controller("/todos", tags=["Todos"])
class TodoController:
    # get all todos
    @http_get("/all", response={200: list[TodoSchema], 400: dict})
    def list_all_todos(self, request):
        try:
            todos = Todo.objects.all()
            return 200, todos
        except Exception as e:
            logger.error(f"Error listing todos: {e}")
            return 400, {"error": str(e)}

    # get todos by user
    @http_get("/", response={200: list[TodoSchema], 400: dict})
    def list_user_todos(self, request):
        try:
            user = request.user
            todos = Todo.objects.filter(user=user)
            return 200, todos
        except Exception as e:
            logger.error(f"Error listing todos: {e}")
            return 400, {"error": str(e)}

    # create todo
    @http_post("/", response={201: TodoSchema, 400: dict})
    def create_todo(self, request, payload: CreateTodoSchema):
        try:
            user = request.user
            todo = Todo.objects.create(user=user, **payload.dict())
            return 201, todo
        except Exception as e:
            logger.error(f"Error creating todo: {e}")
            return 400, {"error": str(e)}

    # get todo by id
    @http_get("/{str:todo_id}", response={200: TodoSchema, 400: dict, 404: dict})
    def get_todo(self, request, todo_id: str):
        try:
            user = request.user
            todo = get_object_or_404(Todo, id=todo_id, user=user)
            return 200, todo
        except Exception as e:
            logger.error(f"Error getting todo: {e}")
            return 400, {"error": str(e)}

    # update todo
    @http_put("/{str:todo_id}", response={200: TodoSchema, 400: dict, 404: dict})
    def update_todo(self, request, todo_id: str, payload: UpdateTodoSchema):
        try:
            user = request.user
            todo = get_object_or_404(Todo, id=todo_id, user=user)
            for key, value in payload.dict().items():
                setattr(todo, key, value)
            todo.save()
            return 200, todo
        except Exception as e:
            logger.error(f"Error updating todo: {e}")
            return 400, {"error": str(e)}

    # delete todo
    @http_delete("/{str:todo_id}", response={204: dict, 400: dict, 404: dict})
    def delete_todo(self, request, todo_id: str):
        try:
            user = request.user
            todo = get_object_or_404(Todo, id=todo_id, user=user)
            todo.delete()
            return 204, {"message": "Todo deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting todo: {e}")
            return 400, {"error": str(e)}
