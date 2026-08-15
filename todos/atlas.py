"""Atlas metadata for the todos app.

The atlas generator reads this module to fill the prose on the map blocks.
See core/atlas.py for the documented shape.
"""

ATLAS = {
    "code": "TD",
    "name": "Todos",
    "what": (
        "The example CRUD resource. Four controller variants demonstrate "
        "progressive abstraction, from declarative to a full service layer."
    ),
    "how": (
        "Route prefix /todos. TodoController (pattern 4) keeps the HTTP "
        "adapter thin and delegates all business logic to TodoService."
    ),
    "children": {
        "controllers": {
            "name": "Controllers",
            "what": "Four patterns: declarative to service layer",
        },
        "services": {
            "name": "Services",
            "what": "TodoService with CRUD + 404 handling",
        },
        "models": {"name": "Models", "what": "Todo with user scoping"},
        "schemas": {"name": "Schemas", "what": "Todo, CreateTodo, UpdateTodo schemas"},
    },
}
