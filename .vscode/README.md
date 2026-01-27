# VSCode Configuration for Django Ninja Boilerplate

Staff engineer-level VSCode configuration optimized for Django development with Ruff.

## Configuration Overview

### `settings.json` - Core Settings

**Clean, focused configuration with only essential settings:**

- **Ruff Integration**: Primary linter and formatter (replaces Black, isort, Flake8)
- **Format on Save**: Automatic code formatting and import organization
- **Python Environment**: Configured for `.venv/bin/python`
- **Django Support**: Proper file associations and environment variables
- **Performance**: Excludes cache directories and build artifacts

### `extensions.json` - Essential Extensions Only

**Minimal set of high-quality extensions:**

- `charliermarsh.ruff` - Modern Python linter/formatter
- `ms-python.python` - Core Python support
- `batisteo.vscode-django` - Django template support
- `ms-azuretools.vscode-docker` - Docker integration
- `esbenp.prettier-vscode` - JSON/YAML formatting
- `eamodio.gitlens` - Git enhancement
- `mikestead.dotenv` - Environment file support

### `launch.json` - Focused Debug Configurations

**Three essential debug scenarios:**

- Django development server
- All tests with pytest
- Current test file

### `tasks.json` - Common Operations

**Six key development tasks:**

- Django server
- Database migrations
- Test execution
- Ruff formatting
- Docker up/down

## Key Features

### Automatic Code Quality

```json
"editor.codeActionsOnSave": {
    "source.organizeImports": "explicit",
    "source.fixAll": "explicit"
}
```

- Removes unused imports automatically
- Sorts imports correctly
- Fixes linting issues on save
- Formats code consistently

### Environment Integration

- Uses project's `.venv/bin/python`
- Loads `.env` file automatically
- Sets `DJANGO_SETTINGS_MODULE` in terminal
- Configures `PYTHONPATH` correctly

### Performance Optimized

- Excludes cache directories from search/file explorer
- Minimal extension set
- Focused file associations
- Disabled unnecessary features

## Usage

### Setup

1. Open workspace: `django-ninja-boilerplate.code-workspace`
2. Install recommended extensions when prompted
3. Configuration works immediately

### Code Quality

- **Format**: Automatic on save
- **Lint**: Shows errors in Problems panel
- **Import Organization**: Automatic on save
- **Manual Format**: `Shift+Alt+F`

### Development Workflow

- **Run Server**: `Ctrl+Shift+P` → "Django: Run Server"
- **Run Tests**: `Ctrl+Shift+P` → "Test: Run All"
- **Debug**: `F5` → Select configuration
- **Format Code**: `Ctrl+Shift+P` → "Ruff: Format & Fix"

## Staff Engineer Standards

✅ **Clean Configuration**: No unused or redundant settings
✅ **Performance**: Fast startup and operation
✅ **Consistency**: Follows project's Ruff configuration
✅ **Minimal Dependencies**: Only essential extensions
✅ **Clear Intent**: Every setting has a purpose
✅ **Standards Compliance**: Follows Django and Python best practices

## Integration Points

- **pyproject.toml**: Ruff settings are centralized here
- **Makefile**: Tasks complement make commands
- **Docker**: Debugging works with containerized setup
- **pytest**: Full test integration and debugging
- **Environment**: Seamless .env and virtual environment handling

This configuration provides a professional, efficient development environment without bloat or unnecessary complexity.
