# Controller patterns

The `todos` app ships four controllers that show increasing levels of
abstraction. Pick the one that matches the task, but prefer pattern 4 for new
work.

| Pattern | File | Use when |
|---|---|---|
| 1 — declarative | `todos/controllers/todo_controller_declarative.py` | Teaching or debugging: every step spelled out with `try/except`. |
| 2 — basic | `todos/controllers/todo_controller_basic.py` | A throwaway endpoint with no shared logic. |
| 3 — partial | `todos/controllers/todo_controller_partial.py` | Reads are trivial, writes need error handling. |
| 4 — full | `todos/controllers/todo_controller.py` | Default. Full decorators plus an injected service. |

## Pattern 4 in full

```python
@api_controller("/todos", tags=["Todos"], auth=JWTAuth())
class TodoController:
    def __init__(self):
        self.service = TodoService()

    @http_get("/{todo_id}", response={200: TodoSchema, 404: dict, 500: dict})
    @log_api_call()
    def get_todo(self, request, todo_id: str):
        return 200, self.service.get_todo(todo_id, request.user)

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    def create_todo(self, request, payload: CreateTodoSchema):
        return 201, self.service.create_todo(payload, request.user)
```

## Decorator rules

- The `@http_*` decorator is outermost.
- `@paginate(...)` sits directly inside `@http_*` on list endpoints.
- `@log_api_call()` sits inside `@http_*` (or `@paginate`) on endpoints that
  need request/response logging.

There is no per-endpoint exception decorator. Domain exceptions are mapped to
HTTP responses by the handlers registered on the shared API instance in
`api/urls.py` (see `api/exceptions`). Just let exceptions propagate: raising
`NotFoundError`, `ValidationError`, etc. from a service returns the matching
status code automatically.

## Pagination

Import `paginate` from `ninja_extra.pagination` and stack it above `@http_get`
on list endpoints. See `TodoController.list_todos`.

## Provider errors

When a controller calls something that can fail on configuration (a provider, a
client, a feature flag), catch the specific exception and return a clear status
with the real message. Do not let the generic 500 handler in `api/exceptions.py`
swallow the detail. See `decisions/controllers/decision_controller.py`.
