from ninja import Schema


class TodoSchema(Schema):
    id: str
    title: str
    description: str
    completed: bool
    created_at: str
    updated_at: str


class CreateTodoSchema(Schema):
    title: str
    description: str
    completed: bool


class UpdateTodoSchema(Schema):
    title: str
    description: str
    completed: bool
