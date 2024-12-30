# Todos App

The todos app is a sample application demonstrating how to build a feature-complete API using Django Ninja. It serves as both a working example and a template for building similar features.

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
python manage.py generate_todos_data

# Specify number of todos to create
python manage.py generate_todos_data --todos 20

# Create todos for a specific user (by username or email)
python manage.py generate_todos_data --user johndoe
python manage.py generate_todos_data --user john@example.com
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
pytest todos/tests.py

# Run specific test class
pytest todos/tests.py::TestTodoModel
pytest todos/tests.py::TestTodoAPI

# Run specific test
pytest todos/tests.py::TestTodoAPI::test_create_todo
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