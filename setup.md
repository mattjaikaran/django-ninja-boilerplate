# Setup

Here I want to document my processes for setting up the project.

1. Create the project directory
```bash
mkdir django-ninja-boilerplate
```

2. Create the virtual environment
```bash
python -m venv env
```

3. Activate the virtual environment
```bash
# On macOS and Linux:
source env/bin/activate
```

On Windows:
env\Scripts\activate

4. Install the dependencies
```bash
pip install -r requirements.txt
```

5. Create the project
```bash
django-admin startproject api .
# this is going to create a new directory called api with the asgi, settings, urls, wsgi files
# if it were not for the dot at the end, it would create a new directory called api with the project inside it 
# ie - django-ninja-boilerplate/api/api
```

6. Create the core app
```bash
python manage.py startapp core
```

7. Create the todos app
```bash
python manage.py startapp todos
```




