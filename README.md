# Django Ninja Boilerplate

A production-ready Django boilerplate using Django Ninja for building modern APIs. Features include JWT authentication, PostgreSQL, Docker support, and comprehensive testing setup.

## Technologies
- Python 3.11
- [Django 5.1](https://docs.djangoproject.com/en/5.1/)
- [Django Ninja](https://django-ninja.dev/)
- [Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) a collection of extra features for Django Ninja 
- [Django Ninja JWT](https://eadwincode.github.io/django-ninja-jwt/)
- [Postgres](https://www.postgresql.org/docs/) database
- [Pydantic](https://docs.pydantic.dev/latest/)
- [Django Unfold Admin](https://unfoldadmin.com/)
- Docker & Docker Compose
- pytest for testing
- Gunicorn for production serving

## Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Create environment file
cp .env.example .env
# Edit .env with your settings

# Start the services
docker-compose up --build
```

Visit http://localhost:8000/api/docs for the API documentation.

## Local Development Setup

```bash
# Create and activate virtual environment
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your settings

# Setup database
make db-setup

# Create superuser
make create-superuser

# Run development server
make runserver
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest path/to/test_file.py

# Run with coverage
pytest --cov=.
```

## Development Tools

- `make startapp <app_name>` - Create a new Django app with extended functionality
- `make lint` - Run linting checks
- `make format` - Format code with Black
- `make generate-core-data` - Generate sample data
- `make db-setup` - Reset and setup database
- `make help` - Show all available commands

## Production Deployment

1. Update `.env` with production settings
2. Build and run with Docker:
```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

## API Documentation
- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`

## Features
- JWT Authentication
- PostgreSQL Database
- Docker & Docker Compose setup
- Comprehensive test setup with pytest
- Code formatting with Black and isort
- Production-ready with Gunicorn
- Environment-based settings
- Custom user model
- Admin panel with Django Unfold
- API throttling and pagination
- CORS configuration
- Debug toolbar for development

## Contributing
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
This project is licensed under the MIT License.