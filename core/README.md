# Core App

The core app is the foundation of the Django Ninja Boilerplate, providing essential functionality including user management, authentication, and base models.

## Features

### Custom User Model
- Extended Django's AbstractBaseUser
- UUID primary key
- Email and username unique fields
- First name and last name fields
- Staff and superuser flags
- Custom user manager with email normalization

### Base Models
- `AbstractBaseModel`: Base model with UUID, created_at, and updated_at fields
- Used as the base for all other models in the project

### Authentication
- JWT-based authentication using django-ninja-jwt
- Token-based API access
- Customizable token lifetime

## API Endpoints

### User Management
- `POST /api/users/signup` - Create new user
- `POST /api/users/superuser` - Create superuser (admin only)
- `GET /api/users/` - List all users
- `GET /api/users/{user_id}` - Get user details
- `PUT /api/users/{user_id}` - Update user
- `DELETE /api/users/{user_id}` - Delete user

## Testing

### Test Structure
The tests are organized into two main classes:
1. `TestUserModel`: Tests for the User model functionality
2. `TestUserAPI`: Tests for the API endpoints

### Reusable Test Fixtures
The following fixtures can be imported and used in other apps' tests:

```python
from core.tests import test_user, test_user_data, auth_headers, create_user

# Available fixtures:
test_password          # Standard test password
test_user_data        # Dictionary of user data
create_user           # Factory function to create users
test_user            # Pre-created test user
auth_token           # JWT token for test_user
auth_headers         # Headers with JWT token for authentication
```

### Running Tests
```bash
# Run all core tests
pytest core/tests.py

# Run specific test class
pytest core/tests.py::TestUserModel
pytest core/tests.py::TestUserAPI

# Run specific test
pytest core/tests.py::TestUserModel::test_create_user
```

### Test Coverage
The tests cover:
- User creation and validation
- Password handling
- Email uniqueness
- Username uniqueness
- Full name generation
- API endpoints
- Authentication
- Authorization
- Data validation

## Development

### Creating a New User
```python
from django.contrib.auth import get_user_model

User = get_user_model()

# Create regular user
user = User.objects.create_user(
    email="user@example.com",
    username="username",
    password="password",
    first_name="First",
    last_name="Last"
)

# Create superuser
admin = User.objects.create_superuser(
    email="admin@example.com",
    username="admin",
    password="password",
    first_name="Admin",
    last_name="User"
)
```

### Using the Base Model
```python
from core.models import AbstractBaseModel

class YourModel(AbstractBaseModel):
    # Your model will automatically have:
    # - UUID primary key
    # - created_at timestamp
    # - updated_at timestamp
    name = models.CharField(max_length=100)
```

## Configuration

### JWT Settings
JWT settings can be configured in `settings.py`:
```python
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ALGORITHM": "HS256",
    # ... other settings
}
``` 