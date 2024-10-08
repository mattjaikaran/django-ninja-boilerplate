#!/bin/bash
echo ">>> First Time Setup script initialization"

# Check if .env file exists, if not, create it from .env.example
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env && echo ".env file created successfully."
    else
        echo "Error: .env.example file not found."
        exit 1
    fi
fi

# Source the .env file
source .env

# Check if required database variables are set
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ] || [ -z "$DB_PASSWORD" ]; then
    echo "Error: Database credentials are not set in .env file."
    echo "Please edit the .env file and set DB_USER, DB_NAME, and DB_PASSWORD."
    exit 1
fi

echo "Database User: $DB_USER"
echo "Database Name: $DB_NAME"
echo "Database Password: $DB_PASSWORD"

# Create and activate virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Apply migrations
python3 manage.py migrate

# Prompt user to create superuser
read -p "Do you want to create a superuser now? (y/n): " create_superuser
if [[ $create_superuser =~ ^[Yy]$ ]]; then
    python3 manage.py create_superuser_interactive
else
    echo "Skipping superuser creation. You can create one later using 'python3 manage.py create_superuser_interactive'"
fi

# Run the server
python3 manage.py runserver