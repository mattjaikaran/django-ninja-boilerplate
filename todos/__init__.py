"""
Todos Application
---------------
This app provides todo management functionality, allowing users
to create, read, update, and delete todo items.
"""

default_app_config = "todos.apps.TodosConfig"

# Import models
from todos.models import Todo

# Import controllers
from todos.controllers import TodoController

__all__ = [
    "Todo",
    "TodoController",
]
