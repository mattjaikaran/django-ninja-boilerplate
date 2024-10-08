#!/bin/bash

# Generate a new Django secret key
generate_django_secret_key() {
    python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
}

# Call the function and store the result
NEW_SECRET_KEY=$(generate_django_secret_key)

# Print the generated secret key to the console
echo "Generated Django Secret Key:"
echo "$NEW_SECRET_KEY"

echo "Add the following line to your .env file:"
echo "SECRET_KEY='$NEW_SECRET_KEY'"
