# todos app

Example app demonstrating **4 API controller patterns** that progress from maximum verbosity to full service-layer abstraction. All four expose the same CRUD surface — only the implementation style differs.

## Pattern Table

| # | Pattern | File | Route Prefix | Description |
|---|---------|------|-------------|-------------|
| 1 | Declarative | `controllers/todo_controller_declarative.py` | `/api/todos-declarative/` | Explicit `try/except` in every method. No decorator magic. Maximum visibility. |
| 2 | Basic | `controllers/todo_controller_basic.py` | `/api/todos-basic/` | No custom decorators. Uses `get_object_or_404`. Cleanest starting point. |
| 3 | Partial | `controllers/todo_controller_partial.py` | `/api/todos-partial/` | Reads are plain; writes use `@handle_exceptions` + `@log_api_call`. |
| 4 | Full (service layer) | `controllers/todo_controller.py` | `/api/todos/` | Full decorator stack + `TodoService` injected via `__init__`. Recommended for production. |

## App Structure

```
todos/
├── controllers/
│   ├── todo_controller.py             # Pattern 4 — full decorators + service layer
│   ├── todo_controller_declarative.py # Pattern 1 — explicit try/except
│   ├── todo_controller_basic.py       # Pattern 2 — minimal, no custom decorators
│   └── todo_controller_partial.py     # Pattern 3 — selective decorators on writes
├── models/
│   └── todo.py                        # Todo model (UUID PK, soft delete, priority)
├── schemas/
│   └── todo_schema.py                 # TodoSchema, CreateTodoSchema, UpdateTodoSchema
├── services/
│   └── todo_service.py                # TodoService: all business logic
├── tests/
│   ├── test_todo.py                   # Integration tests
│   └── factories/
│       └── todo_factory.py            # factory-boy factory for test data
├── admin/
│   └── todo_admin.py                  # Django admin registration
└── management/
    └── commands/
        └── generate_todos_data.py     # Seed command for development data
```

## Pattern Code Examples

### Pattern 1 — Declarative (explicit try/except)

Every method wraps its body in `try/except`. No decorator magic. Every error path is visible in the code.

```python
@http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
def create_todo(self, request, payload: CreateTodoSchema):
    try:
        if not payload.title or not payload.title.strip():
            return 400, {"error": "Validation error", "message": "Title is required"}
        todo_data = payload.model_dump()
        todo_data["user"] = request.user
        todo = Todo.objects.create(**todo_data)
        logger.info("Created todo '%s' (id=%s)", todo.title, todo.id)
        return 201, todo
    except Exception as exc:
        logger.exception("Failed to create todo for user %s", request.user.id)
        return 500, {"error": "Internal server error", "detail": str(exc)}
```

Best for: Learning the framework. Teams that want full transparency with no decorator abstraction.

### Pattern 2 — Basic (no custom decorators)

Uses `get_object_or_404` for 404 handling. Other exceptions propagate to Django Ninja's default handler.

```python
@http_post("/", response={201: TodoSchema})
def create_todo(self, request, payload: CreateTodoSchema):
    todo_data = payload.model_dump()
    todo_data["user"] = request.user
    todo = Todo.objects.create(**todo_data)
    logger.info("Created todo '%s' (id=%s)", todo.title, todo.id)
    return 201, todo

@http_get("/{todo_id}", response={200: TodoSchema, 404: dict})
def get_todo(self, request, todo_id: str):
    return get_object_or_404(
        Todo.objects.select_related("user"), id=todo_id, user=request.user
    )
```

Best for: Small projects. Developers who prefer no abstraction on top of the framework primitives.

### Pattern 3 — Partial (selective decorators)

Read endpoints are undecorated. Write endpoints use `@handle_exceptions` and `@log_api_call` where it matters most.

```python
# Read — no custom decorators
@http_get("/{todo_id}", response={200: TodoSchema, 404: dict})
def get_todo(self, request, todo_id: str):
    return get_object_or_404(Todo, id=todo_id, user=request.user)

# Write — decorated for observability and structured error responses
@http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
@log_api_call(include_payload=True, include_response=False)
@handle_exceptions(return_500_on_error=True, log_errors=True)
def create_todo(self, request, payload: CreateTodoSchema):
    todo_data = payload.model_dump()
    todo_data["user"] = request.user
    return 201, Todo.objects.create(**todo_data)
```

Best for: Teams that want observability on writes but don't need it on simple reads. A practical middle ground.

### Pattern 4 — Full service layer (recommended for production)

Controller is a thin HTTP adapter. All business logic lives in `TodoService`, injected via `__init__`. Methods are one-liners. The service is trivially swappable in tests.

```python
@api_controller("/todos", tags=["Todos"], auth=JWTAuth())
class TodoController:
    def __init__(self):
        self.service = TodoService()

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_todo(self, request, payload: CreateTodoSchema):
        return 201, self.service.create_todo(payload, request.user)

    @http_get("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def get_todo(self, request, todo_id: str):
        return 200, self.service.get_todo(todo_id, request.user)
```

Best for: Production codebases. Multiple controllers sharing business logic. Unit-testing service methods independently.

## The Service Layer

`todos/services/todo_service.py` contains `TodoService`, which encapsulates all database operations and business rules.

```python
class TodoService:
    def list_todos(self, user, search=None, completed=None, priority=None, ordering=None) -> QuerySet: ...
    def get_todo(self, todo_id, user) -> Todo:               # raises Http404 if missing
    def create_todo(self, payload, user) -> Todo: ...
    def update_todo(self, todo_id, payload, user) -> Todo: ...
    def delete_todo(self, todo_id, user) -> None: ...
    def list_completed_todos(self, user) -> QuerySet: ...
    def list_pending_todos(self, user) -> QuerySet: ...
    def search_todos(self, user, q=None, priority=None, completed=None) -> QuerySet: ...
```

Key design decisions:
- Methods raise `Http404` (not `Todo.DoesNotExist`) so the `@handle_exceptions` decorator maps them to a 404 response automatically.
- The service has no knowledge of HTTP — it takes Python types as arguments and returns Django model instances or QuerySets.
- `TodoService` is instantiated once per controller instance (`self.service = TodoService()`) and reused across requests.

## When to Use Which Pattern

```
Starting a new project or learning?
  → Pattern 2 (Basic) — least noise, easiest to read

Want full transparency for debugging?
  → Pattern 1 (Declarative) — every error path is right there in the method

Production app with simple reads and complex writes?
  → Pattern 3 (Partial) — selective decoration where it adds value

Production app, multiple features, team of developers?
  → Pattern 4 (Full service layer) — thin controllers, testable service, easy to extend
```

## API Endpoints

All four controllers expose the same operations (replace `/todos/` with the appropriate prefix):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/todos/` | List todos (paginated, filterable) |
| `GET` | `/api/todos/{id}` | Retrieve a single todo |
| `POST` | `/api/todos/` | Create a todo |
| `PUT` | `/api/todos/{id}` | Update a todo (partial fields) |
| `DELETE` | `/api/todos/{id}` | Delete a todo |
| `GET` | `/api/todos/completed` | List completed todos |
| `GET` | `/api/todos/pending` | List pending todos |
| `GET` | `/api/todos/search` | Advanced search |

Query parameters for list/search endpoints:
- `search` — case-insensitive substring match on title and description
- `completed` — boolean filter (`true`/`false`)
- `priority` — case-insensitive priority label filter
- `ordering` — one of `title`, `-title`, `created_at`, `-created_at`, `updated_at`, `-updated_at`, `priority`, `-priority`

## Example API Usage

```bash
# Create a todo
curl -X POST http://localhost:8000/api/todos/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Todo", "description": "Description", "completed": false}'

# List todos with filter
curl "http://localhost:8000/api/todos/?completed=false&ordering=-created_at" \
  -H "Authorization: Bearer <token>"

# Search
curl "http://localhost:8000/api/todos/search?q=meeting&priority=high" \
  -H "Authorization: Bearer <token>"

# Update
curl -X PUT http://localhost:8000/api/todos/<todo-id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

## Sample Data Generation

```bash
# Create 10 todos for a random user (default)
uv run python manage.py generate_todos_data

# Specify number of todos
uv run python manage.py generate_todos_data --todos 20

# Create todos for a specific user
uv run python manage.py generate_todos_data --user johndoe
uv run python manage.py generate_todos_data --user john@example.com
```

## Running Tests

```bash
# All todos tests
uv run pytest todos/tests/ -v

# Specific file
uv run pytest todos/tests/test_todo.py -v

# Specific class
uv run pytest todos/tests/test_todo.py::TestTodoAPI -v
```
