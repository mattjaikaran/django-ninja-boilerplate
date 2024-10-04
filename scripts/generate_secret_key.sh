#!/bin/bash

# Generate a new Django secret key
generate_django_secret_key() {
    python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
}

# Call the function and store the result
NEW_SECRET_KEY=$(generate_django_secret_key)

# Print the generated secret key
echo "Generated Django Secret Key:"
echo "$NEW_SECRET_KEY"

# Update the SECRET_KEY in the .env file
if [ -f .env ]; then
    # Use sed to replace the existing SECRET_KEY line (macOS compatible)
    sed -i '' "s/^SECRET_KEY=.*$/SECRET_KEY='$NEW_SECRET_KEY'/" .env
    echo "SECRET_KEY updated in .env file"
else
    echo "Error: .env file not found"
fi