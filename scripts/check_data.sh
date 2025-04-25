#!/bin/bash


echo "Checking data..."
python manage.py shell -c "from django.apps import apps; print('\n'.join([f'{model._meta.label}: {model.objects.count()}' for model in apps.get_models() if not model._meta.abstract]))" | cat
