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
    @handle_exceptions()
    @log_api_call()
    def get_todo(self, request, todo_id: str):
        return 200, self.service.get_todo(todo_id, request.user)

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_todo(self, request, payload: CreateTodoSchema):
        return 201, self.service.create_todo(payload, request.user)
```

## Decorator rules the checker enforces

- The `@http_*` decorator is outermost.
- `@handle_exceptions()` is present on every POST, PUT, PATCH, and DELETE.
- `@validate_request()` is innermost when used.
- `@log_api_call()` sits between them.

Both `@log_api_call` then `@handle_exceptions` and the reverse pass, because the
checker only requires `@http_*` before `@handle_exceptions`. Match the `todos`
controller exactly to stay consistent.

## Pagination

Import `paginate` from `ninja_extra.pagination` and stack it above `@http_get`
on list endpoints. See `TodoController.list_todos`.

## Provider errors

When a controller calls something that can fail on configuration (a provider, a
client, a feature flag), catch the specific exception and return a clear status
with the real message. Do not let `@handle_exceptions()` swallow the detail into
a generic 500. See `decisions/controllers/decision_controller.py`.
