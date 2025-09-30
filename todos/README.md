# Todos App

The todos app provides functionality for managing todo items, allowing users to create, read, update, and delete their todos.

## Folder Structure

```
todos/
├── admin/                # Admin interface configurations
│   ├── __init__.py       # Imports all admin classes
│   └── todo_admin.py     # Admin configuration for todo model
├── controllers/          # API controllers/endpoints
│   ├── __init__.py       # Imports all controllers
│   └── todo_controller.py # Todo-related endpoints
├── management/           # Django management commands
│   ├── __init__.py
│   └── commands/         # Custom management commands
│       ├── __init__.py
│       └── generate_todos_data.py # Generates sample todo data
├── migrations/           # Database migrations
├── models/               # Database models
│   ├── __init__.py       # Imports all models
│   └── todo.py           # Todo model
├── schemas/              # API schemas/serializers
│   ├── __init__.py       # Imports all schemas
│   └── todo_schema.py    # Todo-related schemas
├── tests/                # Unit and integration tests
│   ├── __init__.py       # Imports all tests
│   └── test_todo.py      # Todo-related tests
├── __init__.py           # Main app initialization
├── apps.py               # App configuration
└── README.md             # Documentation for the app
```

## Components

### Models

- `Todo`: Model representing a todo item with user relationship, title, description, and completed status

### Controllers

- `TodoController`: Manages CRUD operations for todo items, with proper user permissions

### Schemas

- Todo-related schemas for serialization/deserialization of todo data

### Tests

Comprehensive tests for all components including the Todo model and API endpoints.

### Management Commands

- `generate_todos_data`: Generates sample todo data for development and testing

## Features

### Todo Model

- Inherits from `AbstractBaseModel` (UUID, timestamps)
- User relationship (ForeignKey)
- Title and description fields
- Completion status
- Automatic ordering by creation date

### API Features

- JWT Authentication required for all endpoints
- User-specific todo lists
- CRUD operations (Create, Read, Update, Delete)
- List filtering by user
- Proper error handling
- Input validation using Pydantic schemas

## Sample Data Generation

The app includes a management command to generate sample todo data for testing and development purposes.

### Basic Usage

```bash
# Create 10 todos for a random user (default)
uv run python manage.py generate_todos_data

# Specify number of todos to create
uv run python manage.py generate_todos_data --todos 20

# Create todos for a specific user (by username or email)
uv run python manage.py generate_todos_data --user johndoe
uv run python manage.py generate_todos_data --user john@example.com
```

### Generated Data Features

- Random 4-word titles using Faker
- 3-sentence descriptions
- Random completion status
- Association with specified user or random/new user
- Realistic data suitable for testing and development

## API Endpoints

### Todo Management

- `GET /api/todos/all` - List all todos (admin only)
- `GET /api/todos/` - List user's todos
- `POST /api/todos/` - Create new todo
- `GET /api/todos/{todo_id}` - Get todo details
- `PUT /api/todos/{todo_id}` - Update todo
- `DELETE /api/todos/{todo_id}` - Delete todo

## Testing

### Test Structure

The tests are organized into two main classes:

1. `TestTodoModel`: Tests for the Todo model functionality
2. `TestTodoAPI`: Tests for the API endpoints

### Using Core App Test Fixtures

The todos app tests utilize the core app's test fixtures:

```python
# Import fixtures from core
from core.tests import test_user, auth_headers

# Example test using core fixtures
@pytest.mark.django_db
def test_create_todo(api_client, test_user, auth_headers):
    todo_data = {
        "title": "Test Todo",
        "description": "Description",
        "completed": False
    }
    response = api_client.post(
        "/api/todos/",
        todo_data,
        content_type="application/json",
        **auth_headers
    )
    assert response.status_code == 200
```

### Running Tests

```bash
# Run all todos tests
make test todos/tests/

# Run specific test file
uv run pytest todos/tests/test_todo.py

# Run specific test class
uv run pytest todos/tests/test_todo.py::TestTodoModel

# Run specific test
uv run pytest todos/tests/test_todo.py::TestTodoAPI::test_create_todo
```

### Test Coverage

The tests cover:

- Todo creation
- User-todo relationship
- Authorization checks
- API endpoints
- Data validation
- Error handling
- Security (cannot access other users' todos)

## Development

### Creating a Todo

```python
from todos.models import Todo

# Create a todo for a user
todo = Todo.objects.create(
    user=user,
    title="Complete documentation",
    description="Write comprehensive docs for the project",
    completed=False
)
```

### Schema Validation

The app uses Pydantic schemas for validation:

```python
# Creating a todo with schema validation
from todos.schemas import CreateTodoSchema

todo_data = CreateTodoSchema(
    title="New Todo",
    description="Description",
    completed=False
)
todo = Todo.objects.create(user=request.user, **todo_data.dict())
```

## Security Features

### Authentication

- All endpoints require JWT authentication
- Tokens are validated on each request
- Users can only access their own todos

### Authorization

```python
# Example of authorization check in views
todo = get_object_or_404(Todo, id=todo_id, user=request.user)
```

## Example API Usage

### Creating a Todo

```bash
curl -X POST http://localhost:8000/api/todos/ \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Todo", "description": "Description", "completed": false}'
```

### Listing User's Todos

```bash
curl http://localhost:8000/api/todos/ \
  -H "Authorization: Bearer <your-token>"
```

### Updating a Todo

```bash
curl -X PUT http://localhost:8000/api/todos/<todo-id> \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Todo", "completed": true}'
```
