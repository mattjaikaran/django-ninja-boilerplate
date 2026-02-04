# OpenAPI Tools

This directory contains OpenAPI-related files and tools for API documentation, SDK generation, and API client collection exports.

## Quick Start

```bash
# Export OpenAPI spec only
make openapi

# Generate SDK clients (TypeScript + Python)
make sdk

# Export Postman collection
make postman

# Generate everything
python manage.py export_openapi --all
```

## Directory Structure

After running the export tools, this directory will contain:

```
docs/openapi/
├── README.md                    # This file
├── openapi.json                 # OpenAPI specification (JSON)
├── openapi.yaml                 # OpenAPI specification (YAML)
├── postman_collection.json      # Postman collection
├── insomnia_collection.json     # Insomnia collection
└── sdk/
    ├── typescript/              # TypeScript SDK client
    │   ├── client.ts
    │   ├── package.json
    │   └── tsconfig.json
    └── python/                  # Python SDK client
        ├── __init__.py
        ├── client.py
        └── pyproject.toml
```

## Management Command

The `export_openapi` management command provides a comprehensive tool for OpenAPI operations:

```bash
# Basic export (JSON format)
python manage.py export_openapi

# Export in YAML format
python manage.py export_openapi --format yaml

# Export both JSON and YAML
python manage.py export_openapi --format both

# Generate SDK clients
python manage.py export_openapi --sdk

# Generate TypeScript SDK only
python manage.py export_openapi --sdk-typescript

# Generate Python SDK only
python manage.py export_openapi --sdk-python

# Export Postman collection
python manage.py export_openapi --postman

# Export Insomnia collection
python manage.py export_openapi --insomnia

# Generate everything
python manage.py export_openapi --all

# Validate the OpenAPI spec
python manage.py export_openapi --validate

# Custom output directory
python manage.py export_openapi --output ./api-docs

# Specify API instance
python manage.py export_openapi --api api.urls.api
```

## Standalone Scripts

The OpenAPI tools can also be run as standalone scripts:

### Generate SDK Clients

```bash
# Generate all SDKs
python scripts/openapi/generate_sdk.py docs/openapi/openapi.json

# Generate TypeScript only
python scripts/openapi/generate_sdk.py docs/openapi/openapi.json -l typescript

# Generate Python only
python scripts/openapi/generate_sdk.py docs/openapi/openapi.json -l python

# Custom output directory
python scripts/openapi/generate_sdk.py docs/openapi/openapi.json -o ./client-sdk
```

### Export Postman Collection

```bash
# Export Postman collection
python scripts/openapi/export_postman.py docs/openapi/openapi.json

# Custom output path
python scripts/openapi/export_postman.py docs/openapi/openapi.json -o my_collection.json
```

### Export Insomnia Collection

```bash
# Export Insomnia collection
python scripts/openapi/export_insomnia.py docs/openapi/openapi.json

# Custom output path
python scripts/openapi/export_insomnia.py docs/openapi/openapi.json -o my_insomnia.json
```

### Generate API Changelog

Compare two OpenAPI specifications to generate a changelog:

```bash
# Generate changelog in Markdown format
python scripts/openapi/generate_changelog.py old_spec.json new_spec.json

# Generate changelog in JSON format
python scripts/openapi/generate_changelog.py old_spec.json new_spec.json --format json

# Save to file
python scripts/openapi/generate_changelog.py old_spec.json new_spec.json -o CHANGELOG.md
```

## Using Generated SDKs

### TypeScript SDK

```typescript
import { ApiClient } from './sdk/typescript/client';

// Initialize client
const client = new ApiClient({
  baseUrl: 'http://localhost:8000/api',
  token: 'your-jwt-token',
});

// Make API calls
const response = await client.healthCheck();
console.log(response.data);

// Authenticate
client.setToken('new-token');
```

### Python SDK

```python
from sdk.python import ApiClient, ApiConfig

# Sync client
with ApiClient(ApiConfig(base_url="http://localhost:8000/api")) as client:
    client.set_token("your-jwt-token")
    response = client.health_check()
    print(response.data)

# Async client
async with AsyncApiClient(ApiConfig(base_url="http://localhost:8000/api")) as client:
    client.set_token("your-jwt-token")
    response = await client.health_check()
    print(response.data)
```

## Importing Collections

### Postman

1. Open Postman
2. Click **File** -> **Import**
3. Select `postman_collection.json`
4. The collection will be imported with:
   - Environment variables (`base_url`, `auth_token`)
   - All endpoints organized by tags
   - Example request bodies
   - Authentication configured

### Insomnia

1. Open Insomnia
2. Go to **Application** -> **Preferences** -> **Data**
3. Click **Import Data** -> **From File**
4. Select `insomnia_collection.json`
5. The workspace will be imported with:
   - Environment variables
   - All requests organized by folders
   - Authentication templates

## Validation

The OpenAPI specification can be validated using `openapi-spec-validator`:

```bash
# Install validator
pip install openapi-spec-validator

# Validate via management command
python manage.py export_openapi --validate

# Or validate manually
python -c "
from openapi_spec_validator import validate_spec
import json
with open('docs/openapi/openapi.json') as f:
    spec = json.load(f)
validate_spec(spec)
print('Validation passed!')
"
```

## CI/CD Integration

Add to your CI pipeline to auto-generate documentation on releases:

```yaml
# .github/workflows/docs.yml
name: Generate API Docs

on:
  release:
    types: [published]

jobs:
  generate-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Generate OpenAPI docs
        run: |
          uv run python manage.py export_openapi --all

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: api-docs
          path: docs/openapi/
```

## Best Practices

1. **Version your API**: Update the version in `api/urls.py` when making changes
2. **Generate on release**: Auto-generate docs as part of your release process
3. **Keep changelogs**: Use `generate_changelog.py` to document API changes
4. **Validate specs**: Always validate before publishing

## Troubleshooting

### "Could not find NinjaAPI instance"

Specify the API path explicitly:

```bash
python manage.py export_openapi --api api.urls.api
```

### "PyYAML is required for YAML output"

Install PyYAML:

```bash
pip install pyyaml
```

### "openapi-spec-validator not installed"

Install the validator:

```bash
pip install openapi-spec-validator
```
