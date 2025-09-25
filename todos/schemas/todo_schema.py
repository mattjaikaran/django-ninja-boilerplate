from ninja import Schema


class TodoSchema(Schema):
    id: str
    title: str
    description: str
    completed: bool
    priority: str
    created_at: str
    updated_at: str


class CreateTodoSchema(Schema):
    title: str
    description: str = ""
    completed: bool = False
    priority: str = "medium"


class UpdateTodoSchema(Schema):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    priority: str | None = None
