# Feature Generation System

This Django Ninja boilerplate now includes a powerful CLI system for generating feature modules with optional integrations. This allows you to quickly scaffold complete features with models, controllers, services, tests, and more.

## Quick Start

### Generate a Payments Feature with Stripe

```bash
uv run python manage.py generate_feature payments --provider stripe --platform-type b2c
```

This creates a complete payments app with:

- Payment, PaymentMethod, and PaymentIntent models
- Stripe service integration
- API controllers for payment operations
- Admin interface
- Comprehensive tests
- Email templates (optional)

### Generate Redis Cache Integration

```bash
uv run python manage.py generate_feature redis --minimal
```

This creates:

- Cache service with Redis backend
- Session manager
- Rate limiting functionality
- Cache decorators
- Management API

### Generate RBAC (Role-Based Access Control)

```bash
uv run python manage.py generate_feature rbac --platform-type b2b
```

This creates:

- Role and Permission models
- User-Role assignments with object-level permissions
- Decorators for permission checking
- RBAC service and middleware
- Admin interface for role management

## Available Features

### Payments

- **Provider Options**: `stripe`, `paypal`
- **Platform Types**: `b2c`, `b2b`, `marketplace`, `saas`
- **Optional Flags**: `--no-subscriptions`, `--no-webhooks`, `--minimal`

```bash
# Full Stripe integration with subscriptions and webhooks
uv run python manage.py generate_feature payments --provider stripe

# Minimal payments without subscriptions
uv run python manage.py generate_feature payments --provider stripe --no-subscriptions --minimal

# B2B marketplace with PayPal
uv run python manage.py generate_feature payments --provider paypal --platform-type marketplace
```

### Redis Integration

- Caching service
- Session management
- Rate limiting
- Cache decorators

```bash
# Full Redis integration
uv run python manage.py generate_feature redis

# Minimal cache-only version
uv run python manage.py generate_feature redis --minimal
```

### RBAC (Role-Based Access Control)

- Role and permission management
- Object-level permissions
- User role assignments
- Permission decorators

```bash
# Full RBAC for B2B platform
uv run python manage.py generate_feature rbac --platform-type b2b

# Minimal RBAC for simple apps
uv run python manage.py generate_feature rbac --minimal
```

### Organizations & Teams

- Organization management
- Team hierarchies
- Member roles and permissions

```bash
# Organization management for B2B
uv run python manage.py generate_feature organization --platform-type b2b

# Team management
uv run python manage.py generate_feature team --platform-type saas
```

### Other Features

- `subscription` - Subscription management
- `notification` - Notification system
- `chat` - Real-time messaging (uses Centrifugo with `--realtime` flag)
- `file_storage` - File upload and storage
- `analytics` - Event tracking and analytics
- `graphql` - Strawberry GraphQL API setup

## Platform Types

### B2C (Business to Consumer)

- Individual user accounts
- Simple permission structure
- Consumer-focused features

### B2B (Business to Business)

- Organization-based accounts
- Complex permission hierarchies
- Team collaboration features

### Marketplace

- Multi-vendor support
- Vendor management
- Commission tracking

### SaaS (Software as a Service)

- Tenant isolation
- Subscription billing
- Feature flags

## Customization Options

### Minimal Mode

Use `--minimal` flag to generate a basic version without advanced features:

- Fewer dependencies
- Simpler models
- Basic functionality only

### Provider Selection

Choose specific providers for external services:

- **Payments**: Stripe, PayPal
- **Storage**: AWS S3, Google Cloud, Local
- **Email**: SendGrid, Mailgun, SMTP

### Custom App Names

Override the default app name:

```bash
uv run python manage.py generate_feature payments --app-name billing
```

## Generated Structure

Each feature generates a complete Django app with:

```
feature_name/
├── models/           # Database models
├── schemas/          # API schemas (Pydantic)
├── controllers/      # API endpoints (Django Ninja)
├── services/         # Business logic
├── admin/           # Django admin configuration
├── tests/           # Comprehensive test suite
├── management/      # Django management commands
│   └── commands/
├── migrations/      # Database migrations
└── README.md        # Feature documentation
```

## Integration Features

### Automatic Settings Updates

- Adds new apps to `INSTALLED_APPS`
- Updates database settings
- Configures cache backends
- Sets up external service credentials

### Dependency Management

- Updates `pyproject.toml` with required packages
- Handles version compatibility
- Optional dependencies based on features

### URL Configuration

- Automatically registers API controllers
- Updates main `urls.py`
- Configures API routing

## Email Service Integration

The boilerplate now includes a comprehensive email service:

### Features

- Multiple backends (Django, Simple)
- Template-based emails
- Bulk email support
- Error handling and logging

### Usage

```python
from core.services.email import default_email_service

# Send welcome email
default_email_service.send_templated_email(
    template_data={
        "html_template": "emails/welcome.html",
        "context": {"user_name": "John", "site_name": "MyApp"}
    },
    recipient_email="user@example.com"
)
```

### Templates

- HTML and text versions
- Context variables
- Subject line templates
- Responsive design

## Examples

### Complete E-commerce Setup

```bash
# Generate payments with Stripe
uv run python manage.py generate_feature payments --provider stripe --platform-type marketplace

# Add organization management
uv run python manage.py generate_feature organization --platform-type marketplace

# Add RBAC for vendor permissions
uv run python manage.py generate_feature rbac --platform-type marketplace

# Add Redis for caching and sessions
uv run python manage.py generate_feature redis
```

### SaaS Application Setup

```bash
# Generate subscription management
uv run python manage.py generate_feature subscription --provider stripe --platform-type saas

# Add team management
uv run python manage.py generate_feature team --platform-type saas

# Add notification system
uv run python manage.py generate_feature notification

# Add analytics tracking
uv run python manage.py generate_feature analytics
```

### Simple API Setup

```bash
# Basic Redis caching
uv run python manage.py generate_feature redis --minimal

# Simple RBAC
uv run python manage.py generate_feature rbac --minimal

# File storage
uv run python manage.py generate_feature file_storage --provider local --minimal
```

## Best Practices

1. **Start with Core Features**: Begin with authentication, then add payments, caching, etc.
2. **Choose the Right Platform Type**: This affects the complexity and features generated
3. **Use Minimal Mode for Prototyping**: Add full features later as needed
4. **Test Generated Code**: Run tests after generation to ensure everything works
5. **Customize as Needed**: The generated code is a starting point, modify to fit your needs

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure to run migrations after generating features
2. **Missing Dependencies**: Check that all required packages are installed
3. **URL Conflicts**: Ensure no duplicate URL patterns
4. **Settings Conflicts**: Review settings updates for any conflicts

### Getting Help

1. Check the generated README.md files in each feature
2. Run the test suite to identify issues
3. Review the Django logs for errors
4. Check the admin interface for model registration

### GraphQL (Strawberry)

Generate a complete GraphQL setup with Strawberry for any Django app:

```bash
# Generate GraphQL for the core app
uv run python manage.py generate_feature graphql --app-name=core

# Generate for a custom app
uv run python manage.py generate_feature graphql --app-name=todos
```

This creates:
- `app/graphql/` - GraphQL package with schema, queries, mutations, and types
- `app/graphql.py` - JWT-authenticated GraphQL view
- Automatic URL configuration for `/graphql/` endpoint

See the main [README.md](README.md#graphql-optional) for usage examples.

## Future Enhancements

- Machine learning model integration
- API versioning support
- Docker configuration generation
