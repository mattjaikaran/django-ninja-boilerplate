from typing import List
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from .models import Todo
from .schemas import TodoSchema, CreateTodoSchema, UpdateTodoSchema


@api_controller("/todos", tags=["Todos"])
class TodoController:
    # get all todos
    @http_get("/all")
    def list_todos(self, request, payload: List[TodoSchema] = None):
        try:
            todos = Todo.objects.all()
            return todos
        except Exception as e:
            return {"error": str(e)}, 400

    # get todos by user
    @http_get("/")
    def list_todos(self, request, payload: List[TodoSchema] = None):
        try:
            user = request.user
            todos = Todo.objects.filter(user=user)
            return todos
        except Exception as e:
            return {"error": str(e)}, 400

    # create todo
    @http_post("/")
    def create_todo(self, request, payload: CreateTodoSchema):
        try:
            user = request.user
            todo = Todo.objects.create(user=user, **payload.dict())
            return todo
        except Exception as e:
            return {"error": str(e)}, 400

    # get todo by id
    @http_get("/{str:todo_id}")
    def get_todo(self, request, todo_id: str):
        try:
            user = request.user
            todo = get_object_or_404(Todo, id=todo_id, user=user)
            return todo
        except Exception as e:
            return {"error": str(e)}, 400

    # update todo
    @http_put("/{str:todo_id}")
    def update_todo(self, request, todo_id: str, payload: UpdateTodoSchema):
        try:
            user = request.user
            todo = get_object_or_404(Todo, id=todo_id, user=user)
            for key, value in payload.dict().items():
                setattr(todo, key, value)
            todo.save()
            return todo
        except Exception as e:
            return {"error": str(e)}, 400

    # delete todo
    @http_delete("/{str:todo_id}")
    def delete_todo(self, request, todo_id: str):
        try:
            user = request.user
            todo = get_object_or_404(Todo, id=todo_id, user=user)
            todo.delete()
            return {"message": "Todo deleted successfully"}
        except Exception as e:
            return {"error": str(e)}, 400
