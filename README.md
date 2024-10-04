# Django Ninja Boilerplate

This project is a boilerplate for a Django application using Django Ninja and Django Unfold. It provides a structured way to build and manage a Django project with these frameworks.

## Technologies
- Python 3.11
- [Django 5.1](https://docs.djangoproject.com/en/5.1/)
- [Django Ninja](https://django-ninja.dev/)
- [Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) a collection of extra features for Django Ninja 
- [Django Ninja JWT](https://eadwincode.github.io/django-ninja-jwt/)
    - [Django Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/) abstraction for Django Ninja
- [Postgres](https://www.postgresql.org/docs/) database
- [Pydantic](https://docs.pydantic.dev/latest/)
- [Django Unfold Admin](https://unfoldadmin.com/)
    - [Unfold Docs](https://github.com/unfoldadmin/django-unfold)
- [Faker](https://faker.readthedocs.io/en/master/) for generating fake data



#### Dev
- Makefile to run commands
- PyTest for unit tests
- [Swagger](https://swagger.io/) for API documentation
  - [Localhost Docs](http://localhost:8000/api/docs)
- [Debug Toolbar](https://django-debug-toolbar.readthedocs.io/en/latest)
- Linting
    - [Black](https://github.com/psf/black) Formatter
        - Configuration located in `@/.vscode/settings.json`
    - [isort](https://pycqa.github.io/isort/) sorting imports
    - [Flake8](https://flake8.pycqa.org/en/latest/)
    - Will run all 3 with the lint script located in `@/scripts/lint.sh`
        - To run `./scripts/lint.sh`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/mattjaikaran/django-ninja-boilerplate.git
   ```

2. Create a virtual environment:

    ```bash
    python -m venv env
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Activate the virtual environment:

    ```bash
    source env/bin/activate
    ```

5. Apply migrations:

    ```bash
    python manage.py migrate
    ```

6. Start the development server:

    ```bash
    python manage.py runserver
    ```
