"""Todos Application
---------------
This app provides todo management functionality, allowing users
to create, read, update, and delete todo items.
"""

default_app_config = "todos.apps.TodosConfig"

# Import models
# Import controllers
from todos.controllers import TodoController
from todos.models import Todo

__all__ = [
    "Todo",
    "TodoController",
]
