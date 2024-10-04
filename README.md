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

```bash
$ git clone https://github.com/mattjaikaran/django-ninja-boilerplate
$ cd django-ninja-boilerplate
$ python3 -m venv env # creat a virtual environment using the venv virtual environment
$ source env/bin/activate # activate the virtual environment
$ touch .env # create a new env file
# update the .env file with necessary values -> db info, superuser info
$ pip3 install -r requirements.txt # install dependencies from requirements.txt
$ python3 manage.py migrate # apply migration files to your local db
$ python3 manage.py create_superuser # runs custom script to create a superuser
$ ./scripts/generate_secret_key.sh # generate new secret key 
$ python3 manage.py runserver # run the local server on http://localhost:8000/admin
```


### Django Ninja Serialization

- Django Ninja uses Pydantic models (Schemas) for serialization, not Django serializers like in DRF.
- The response parameter in the route decorator specifies the expected response format.
- Use from_orm() to convert Django ORM objects to Pydantic models.
- Django Ninja automatically handles the conversion to JSON in the HTTP response.

## Admin Panel
- [Django Unfold Docs](https://github.com/unfoldadmin/django-unfold)

Django Unfold has one of the cleaniest designs for Django admin panels. Pretty easy to get set up and there is now support for certain libraries that broke the design (ie - django-import-export)


## API Docs

Using Swagger for documentation

If the server is running, you can see the docs located at [localhost:8000/api/docs](http://localhost:8000/api/docs)