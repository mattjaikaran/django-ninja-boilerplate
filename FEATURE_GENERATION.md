# Feature generation

`manage.py generate_feature` creates a Django app for one feature and wires it
into the project. Each generated app follows the conventions in `AGENTS.md`:
`JWTAuth` controllers, services that hold every query, `CamelCaseSchema`
schemas and one smoke and permission test file.

```bash
uv run python manage.py generate_feature <feature> [--app-name NAME] [options]
```

A generator does these steps:

1. Creates the app with `startapp_extended` and replaces its CRUD scaffold.
2. Adds the app to `INSTALLED_APPS` in `api/settings/common.py`.
3. Registers its controllers in `api/urls.py`.
4. Runs `makemigrations` for the app and then `migrate`. A failed `migrate`
   only logs a warning, for example when the database is not running. The
   `redis` and `graphql` features have no models and skip this step.

The `payments`, `notification`, `chat`, `organization`, `analytics` and
`api_endpoint` generators refuse an app name that already exists, so they
never overwrite an app such as `billing` or `notifications`.

## Audit logging of generated models

Every model is audited by default. The `pre_save`, `post_save` and
`post_delete` handlers in `core/audit/signals.py` write one `AuditLog` row
per create, update and delete. That is correct for user-facing records, but
an append-only or high-volume table (ingest rows, outbox events, event logs,
line snapshots) writes an audit row for every insert.

Exclude those models in `api/settings/common.py`:

```python
AUDIT_EXCLUDED_MODELS = [
    *AUDIT_EXCLUDED_MODELS,
    "IngestRow",
    "OutboxEvent",
    "LineSnapshot",
]
```

Or audit only a small allowlist. When `AUDIT_TRACKED_MODELS` is not `None`,
it replaces the "every model except the exclusions" default:

```python
AUDIT_TRACKED_MODELS = ["User", "Payment", "Subscription"]
```

`should_track_model` reads both settings on every signal, so restart the app
after a change. The generated app README repeats this note for the model it
creates.

## App names

Without `--app-name`, the app name is the feature type: `generate_feature team`
creates the `team` app. The `redis` feature defaults to `cache_api`.

The command refuses an app name that shadows an installed Python module, for
example `redis` or `graphql`, and tells you to pass `--app-name`. The
`graphql` feature adds GraphQL to an existing app, so always pass
`--app-name` for it.

## Features

| Feature | Default app | Routes |
|---|---|---|
| `payments` | `payments` | `/api/payments/*` |
| `redis` | `cache_api` | `/api/cache/*` |
| `rbac` | `rbac` | `/api/rbac/*` |
| `organization` | `organization` | `/api/organizations/*`, `/api/invitations/*` |
| `team` | `team` | `/api/teams/*` |
| `notification` | `notification` | `/api/notifications/*` |
| `chat` | `chat` | `/api/conversations/*`, `/api/messages/*` |
| `analytics` | `analytics` | `/api/analytics/*` |
| `api_endpoint` | `api_endpoint` | `/api/<plural of the app name>/*` |
| `graphql` | none, pass `--app-name` | `POST /api/graphql/` |

### Payments

```bash
uv run python manage.py generate_feature payments --provider stripe
uv run python manage.py generate_feature payments --no-subscriptions
```

This creates:

- Payment, PaymentMethod, PaymentIntent and StripeCustomer models, plus
  SubscriptionPlan and Subscription unless you pass `--no-subscriptions`
- `PaymentService`: owner-scoped queries and every Stripe call. It raises
  `ImproperlyConfigured` when `STRIPE_SECRET_KEY` is empty
- `PaymentController` at `/api/payments/*` with `JWTAuth`
- Admin interface
- One smoke and permission test file. The tests do not call Stripe: they
  cover the owner scoping, validation and auth boundary of the Stripe routes

### Redis or Valkey cache

```bash
uv run python manage.py generate_feature redis
```

This creates the `cache_api` app with a staff-only (`IsAdminUser`) cache API.
It uses Django's cache framework, so it works with the `CACHES` backend that
`api/settings` builds from `REDIS_URL` or `VALKEY_URL`. It adds no models,
settings or dependencies.

- `GET /api/cache/health`: writes, reads and deletes a probe key and returns
  the backend name and the round-trip time
- `DELETE /api/cache/keys/{key}`: deletes one key, or returns 404 when the
  key is not cached
- Smoke and permission tests in `cache_api/tests/test_cache.py`

### RBAC (role-based access control)

```bash
uv run python manage.py generate_feature rbac
```

This creates:

- Role and Permission models
- User-role assignments, global or on one object
- A `JWTAuth` controller at `/api/rbac/*`. Role, permission and assignment
  routes need `IsAdminUser`; a regular user may call only
  `GET /api/rbac/me/permissions` for their own roles and permissions
- Decorators for permission checking, an RBAC service and middleware
- Admin interface for role management
- Smoke and permission tests in `rbac/tests/test_rbac.py`

### Organizations and teams

```bash
uv run python manage.py generate_feature organization
uv run python manage.py generate_feature organization --minimal
uv run python manage.py generate_feature team
```

- Organizations at `/api/organizations/*` and invitations at
  `/api/invitations/*`: members see their organizations, owners and admins
  manage them, and invited users accept or decline their own invitations.
  The generator adds `ORGANIZATION_INVITATION_EXPIRY_DAYS = 7` and
  `ORGANIZATION_MAX_MEMBERS` to the settings: 1000, or 100 with `--minimal`
- Teams at `/api/teams/*`: members see their teams, team leads manage the
  team and its members

### Notifications

```bash
uv run python manage.py generate_feature notification
```

This creates notifications and notification preferences at
`/api/notifications/*`, scoped to the user: list, unread, count, mark one or
all as read, delete, and read or update preferences.

### Chat

```bash
uv run python manage.py generate_feature chat
uv run python manage.py generate_feature chat --realtime
```

This creates messaging at `/api/conversations/*` and `/api/messages/*`, scoped
to the conversations the user takes part in. It adds
`CHAT_MESSAGE_MAX_LENGTH` and `CHAT_CONVERSATION_MAX_PARTICIPANTS` to the
settings. `--realtime` also creates `ChatRealtimeService` in
`<app>/services/chat_realtime_service.py`, which publishes chat events to
Centrifugo (see `docs/REALTIME.md`).

### Analytics

```bash
uv run python manage.py generate_feature analytics
```

This creates product event tracking. It adds no settings or dependencies.

- An `Event` model: the user, an event name such as `report.exported`, and a
  `properties` object of up to 50 scalar values
- `POST /api/analytics/events`: records an event for the user. Names are
  lowercase letters, digits and `_.:-`
- `GET /api/analytics/events?name=`: the user's newest 100 events
- `GET /api/analytics/summary?days=30`: staff only (`IsAdminUser`). Event
  counts per name across all users over the last 1 to 365 days
- Smoke, ownership and permission tests in `analytics/tests/test_analytics.py`

### API endpoint

```bash
uv run python manage.py generate_feature api_endpoint --app-name widgets
```

This creates an owner-scoped CRUD resource from the `startapp_extended`
templates: a `Widget` model, schemas, service and a `JWTAuth` controller at
`/api/widgets/*`.

Pass `--layers` to choose the layer set. The default is `repository`.

- `repository`: The controller calls a service, the service calls a
  repository, and the repository returns model instances. Creates
  `repositories/`.
- `service`: The controller calls a service that queries the models directly.
  Creates no repository.
- `dto`: The repository returns frozen dataclass DTOs, so the service and the
  controller never see model instances. Creates `repositories/` and `dtos/`.

### Engine

```bash
uv run python manage.py generate_feature engine --app-name booking --modules artists,tours
```

This creates `engines/booking/` with one Django app per module
(`engines.booking.artists`, `engines.booking.tours`). Each module gets a
model, a repository that returns frozen-dataclass DTOs, a service, schemas,
a `JWTAuth` controller at `/api/booking/<module>/` and boundary tests. The
engine gets a README and an engine service for cross-module flows. Without
`--modules`, the engine has one module named after it. Read
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#engines-optional-modular-layer)
before you add one.

### GraphQL (Strawberry)

```bash
# Add GraphQL to the core app
uv run python manage.py generate_feature graphql --app-name=core

# Add GraphQL to another existing app
uv run python manage.py generate_feature graphql --app-name=todos
```

This creates:

- `app/graphql/` - GraphQL package with schema, queries, mutations, types,
  permission classes and a user service that scopes every query to the viewer
- `app/tests/test_graphql.py` - Smoke and permission tests for `POST /api/graphql/`
- `graphql_view.py` in `core` - JWT-authenticated GraphQL view
- Automatic URL configuration for the `POST /api/graphql/` endpoint

Install the dependencies first with `uv sync --extra graphql`. See the main
[README.md](README.md#graphql-optional) for usage examples.

## Options

| Option | Applies to | Effect |
|---|---|---|
| `--app-name NAME` | every feature | Name of the app to create or extend |
| `--provider stripe` | `payments` | The payments provider. Only `stripe` exists |
| `--platform-type` | `payments`, `rbac`, `organization`, `team` | Shown in the generator log only. It does not change the generated code |
| `--no-subscriptions` | `payments` | Skip the SubscriptionPlan and Subscription models |
| `--minimal` | `organization` | Set `ORGANIZATION_MAX_MEMBERS` to 100 instead of 1000 |
| `--realtime` | `chat` | Add `ChatRealtimeService` for Centrifugo |
| `--modules a,b` | `engine` | Module names, comma-separated. Defaults to one module named after the engine |
| `--layers service\|repository\|dto` | `api_endpoint` | Layer set for the generated app. Default: `repository` |

Other generators accept `--minimal` and `--platform-type` but ignore them.

## Removed features

- `subscription`: it created only the generic `startapp_extended` scaffold.
  Use `generate_feature payments`, which creates SubscriptionPlan and
  Subscription, or the existing `billing` app.
- `file_storage`: it created only the generic scaffold. Use the existing
  `files` app: set `FILES_ENABLED=true` for owner-scoped local and S3
  uploads.
- `monitoring` and `cache`: these choices had no generator. Use `redis` for
  the cache API.

## Verify the generators

```bash
just check-generators
uv run python scripts/check_generators.py --only analytics,redis
```

The GENERATORS gate runs every generator in a throwaway worktree, then runs
`manage.py check`, a pending-migrations check, ruff and the generated tests.
Your working tree does not change.

After you generate a feature in your tree, run its test file, then
`just openapi` to update `docs/openapi/openapi.json`. Add each new anonymous
route to `PUBLIC_OPERATIONS` in `core/tests/test_route_auth.py` only after
you review it. Verify the feature itself with a Playwright journey in the
frontend (see `docs/product/README.md`).

## Email service integration

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
