# Architecture Documentation

This document provides a comprehensive overview of the Django Ninja Boilerplate architecture, including system design, component relationships, and deployment strategies.

## Table of Contents

- [System Overview](#system-overview)
- [Application Architecture](#application-architecture)
- [Progressive Controller Patterns](#progressive-controller-patterns)
- [Docker Architecture](#docker-architecture)
- [Database Schema](#database-schema)
- [API Design](#api-design)
- [Authentication Flow](#authentication-flow)
- [Background Tasks](#background-tasks)
- [Real-Time Messaging](./REALTIME.md) (Centrifugo)
- [Deployment Options](#deployment-options)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPLICATIONS                             │
│                    (Web, Mobile, IoT, Third-party Services)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOAD BALANCER / CDN                            │
│                         (Nginx, CloudFlare, AWS ALB)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
          ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
          │  Django API     │ │  Django API     │ │  Django API     │
          │  Instance 1     │ │  Instance 2     │ │  Instance N     │
          │  (Gunicorn)     │ │  (Gunicorn)     │ │  (Gunicorn)     │
          └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                   │                   │                   │
                   └───────────────────┼───────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
     ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
     │   PostgreSQL    │      │     Redis       │      │   Celery        │
     │   (Primary DB)  │      │ (Cache/Broker)  │      │   Workers       │
     └─────────────────┘      └─────────────────┘      └─────────────────┘
```

### Component Summary

| Component | Purpose | Technology |
|-----------|---------|------------|
| **API Server** | REST API endpoints | Django Ninja + Gunicorn |
| **Database** | Persistent data storage | PostgreSQL 17 |
| **Cache/Broker** | Caching & message queue | Redis 7.2 |
| **Task Queue** | Background job processing | Celery |
| **Scheduler** | Periodic task scheduling | Celery Beat |
| **Monitoring** | Task monitoring UI | Flower |
| **Tracing** | Distributed tracing | OpenTelemetry + Jaeger |
| **Metrics** | Application metrics | Prometheus |
| **Real-Time** | WebSocket messaging | Centrifugo v5 |
| **Audit Log** | Compliance tracking | Django signals + middleware |
| **Feature Flags** | Gradual rollouts & A/B testing | Custom service |

---

## Application Architecture

### Django App Structure

```
django-ninja-boilerplate/
│
├── api/                          # API Configuration & Utilities
│   ├── settings/                 # Environment-specific settings
│   │   ├── common.py            # Shared settings
│   │   ├── dev.py               # Development overrides
│   │   ├── prod.py              # Production overrides
│   │   └── test.py              # Test settings (SQLite locally, PostgreSQL in CI)
│   ├── pagination/              # Pagination utilities
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── offset.py            # Offset-based pagination
│   │   ├── cursor.py            # Cursor-based pagination
│   │   └── decorators.py        # View decorators
│   ├── throttling/              # Rate limiting
│   │   ├── limiter.py           # Rate limiter classes
│   │   └── decorators.py        # Throttle decorators
│   ├── utils/                   # HTTP utilities
│   ├── centrifugo.py            # Centrifugo JWT tokens + HTTP client
│   ├── decorators.py            # API decorators
│   ├── exceptions.py            # Custom exceptions
│   ├── middleware.py            # Request/Response middleware
│   └── urls.py                  # URL routing
│
├── core/                         # Core Application (Users/Auth)
│   ├── controllers/             # API Controllers
│   │   ├── auth_controller.py   # JWT authentication
│   │   ├── centrifugo_controller.py # Real-time token endpoints
│   │   ├── user_controller.py   # User management
│   │   └── otp_controller.py    # OTP/Magic link auth
│   ├── audit/                   # Audit logging system
│   │   ├── models.py            # AuditLog model
│   │   ├── middleware.py        # Request logging
│   │   ├── signals.py           # Model change tracking
│   │   └── decorators.py        # @audit_action
│   ├── features/                # Feature flags
│   │   ├── models.py            # FeatureFlag model
│   │   ├── service.py           # Flag evaluation
│   │   └── middleware.py        # Request flag attachment
│   ├── observability/           # Monitoring & tracing
│   │   ├── tracing.py           # OpenTelemetry setup
│   │   ├── metrics.py           # Prometheus metrics
│   │   ├── logging.py           # Structured logging
│   │   └── health.py            # Health checks
│   ├── tasks/                   # Task management
│   │   ├── base.py              # ProgressTask, CriticalTask
│   │   ├── progress.py          # Progress tracking
│   │   ├── dlq.py               # Dead Letter Queue
│   │   └── scheduler.py         # Periodic tasks
│   ├── models/                  # Django models
│   ├── schemas/                 # Request/Response schemas
│   ├── services/                # Business logic
│   └── tests/                   # Unit tests
│
├── todos/                        # Example Feature App
│   ├── controllers/             # Todo API controllers
│   ├── models/                  # Todo model
│   ├── schemas/                 # Todo schemas
│   └── tests/                   # Todo tests
│
└── cli/                          # CLI Tool (separate package)
    └── src/django_ninja_matt/
        ├── commands/            # CLI commands
        └── generators/          # Project generators
```

### Request Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  Nginx   │────▶│ Gunicorn │────▶│  Django  │────▶│Controller│
│ Request  │     │  Proxy   │     │  Worker  │     │Middleware│     │  (View)  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                                          │
                                                                          ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │◀────│  Nginx   │◀────│ Gunicorn │◀────│  Django  │◀────│ Service  │
│ Response │     │  Proxy   │     │  Worker  │     │Middleware│     │  Layer   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                                          │
                                                                          ▼
                                                                   ┌──────────┐
                                                                   │ Database │
                                                                   │ / Cache  │
                                                                   └──────────┘
```

### Layer Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Controllers   │  │     Schemas     │  │   Decorators    │             │
│  │  (API Routes)   │  │ (Validation)    │  │ (Auth/Logging)  │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             BUSINESS LAYER                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │    Services     │  │   Validators    │  │     Utils       │             │
│  │ (Business Logic)│  │ (Domain Rules)  │  │   (Helpers)     │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │     Models      │  │    Managers     │  │   QuerySets     │             │
│  │  (ORM Entities) │  │ (Custom Queries)│  │  (Filtering)    │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Progressive Controller Patterns

The `todos` app ships four controller variants that demonstrate a progression from maximum verbosity to full service-layer abstraction. All four expose the same CRUD surface — only the implementation style differs.

### Pattern Summary

| Pattern | File | Route Prefix | When to Use |
|---------|------|-------------|-------------|
| **1 — Declarative** | `todo_controller_declarative.py` | `/api/todos-declarative/` | Learning the framework; teams that want full visibility into every error path |
| **2 — Basic** | `todo_controller_basic.py` | `/api/todos-basic/` | Small projects; developers who prefer minimal abstraction |
| **3 — Partial** | `todo_controller_partial.py` | `/api/todos-partial/` | When reads are simple but writes need structured error handling and logging |
| **4 — Full (service layer)** | `todo_controller.py` | `/api/todos/` | Production code; teams with multiple controllers sharing business logic |

### Controller to Service Layer Relationship

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONTROLLER LAYER                            │
│                  (HTTP concerns only)                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Declarative  │  │    Basic     │  │   Partial    │         │
│  │(try/except)  │  │(get_or_404) │  │ (selective   │         │
│  │              │  │              │  │  decorators) │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Full — @handle_exceptions + @log_api_call + service    │  │
│  │         ↓ delegates all logic to TodoService            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                (Pattern 4 only — others hit DB directly)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER                              │
│               todos/services/todo_service.py                    │
│                                                                 │
│  TodoService                                                    │
│  ├── list_todos(user, search, completed, priority, ordering)    │
│  ├── get_todo(todo_id, user)          → Todo | Http404          │
│  ├── create_todo(payload, user)       → Todo                    │
│  ├── update_todo(todo_id, payload, user) → Todo | Http404       │
│  ├── delete_todo(todo_id, user)       → None | Http404          │
│  ├── list_completed_todos(user)       → QuerySet                │
│  ├── list_pending_todos(user)         → QuerySet                │
│  └── search_todos(user, q, priority, completed) → QuerySet      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                │
│               todos/models/todo.py (ORM)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Pattern Comparison

**Pattern 1 — Declarative** (`todo_controller_declarative.py`)

Every method wraps its body in `try/except`. No decorator magic. Best for teams that want every error path explicit in the code rather than handled by a shared decorator.

```python
@http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
def create_todo(self, request, payload: CreateTodoSchema):
    try:
        todo_data = payload.model_dump()
        todo_data["user"] = request.user
        todo = Todo.objects.create(**todo_data)
        return 201, todo
    except Exception as exc:
        logger.exception("Failed to create todo")
        return 500, {"error": "Internal server error", "detail": str(exc)}
```

**Pattern 2 — Basic** (`todo_controller_basic.py`)

Uses `get_object_or_404` for lookup safety. No custom decorators. Errors that aren't 404s propagate to Django Ninja's default exception handler. Best as a clean starting point.

```python
@http_post("/", response={201: TodoSchema})
def create_todo(self, request, payload: CreateTodoSchema):
    todo_data = payload.model_dump()
    todo_data["user"] = request.user
    todo = Todo.objects.create(**todo_data)
    return 201, todo
```

**Pattern 3 — Partial** (`todo_controller_partial.py`)

Reads are undecorated. Writes use `@handle_exceptions` and `@log_api_call`. Shows that you can mix and match rather than applying decorators uniformly.

```python
# Read — no decorators needed
@http_get("/{todo_id}", response={200: TodoSchema, 404: dict})
def get_todo(self, request, todo_id: str):
    return get_object_or_404(Todo, id=todo_id, user=request.user)

# Write — decorated for observability and error handling
@http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
@log_api_call(include_payload=True, include_response=False)
@handle_exceptions(return_500_on_error=True, log_errors=True)
def create_todo(self, request, payload: CreateTodoSchema):
    todo_data = payload.model_dump()
    todo_data["user"] = request.user
    return 201, Todo.objects.create(**todo_data)
```

**Pattern 4 — Full service layer** (`todo_controller.py`) — recommended for production

Controller is a thin HTTP adapter. All business logic lives in `TodoService`, injected via `__init__`. Methods are one-liners. The service is trivially swappable in tests.

```python
class TodoController:
    def __init__(self):
        self.service = TodoService()

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_todo(self, request, payload: CreateTodoSchema):
        return 201, self.service.create_todo(payload, request.user)
```

### Decorator Stack (Patterns 3 and 4)

```
HTTP POST /todos/
     │
     ▼
@log_api_call          — logs request start/end, payload, duration
     │
     ▼
@handle_exceptions     — catches exceptions → structured 500 response
     │
     ▼
@validate_request      — runs extra schema validation before handler
     │
     ▼
def create_todo()      — thin handler, delegates to service
     │
     ▼
TodoService.create_todo()  — business logic, ORM calls
```

---

## Docker Architecture

### Multi-Stage Build Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1: BUILDER                                    │
│                                                                             │
│   python:3.13-slim                                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Install build tools (gcc, build-essential)                       │  │
│   │  • Install uv package manager                                       │  │
│   │  • Create virtual environment                                       │  │
│   │  • Install Python dependencies                                      │  │
│   │                                                                     │  │
│   │  Size: ~800MB (includes compilers, headers)                        │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ COPY /opt/venv
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STAGE 2: PRODUCTION                                   │
│                                                                             │
│   python:3.13-slim                                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Runtime libraries only (libpq5, curl)                           │  │
│   │  • Virtual environment from builder                                 │  │
│   │  • Application code                                                 │  │
│   │  • Non-root user (security)                                        │  │
│   │  • Health checks                                                    │  │
│   │                                                                     │  │
│   │  Size: ~250MB (minimal runtime)                                    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Docker Compose Services

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        docker-compose.yml (Development)                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│     db      │     │    redis    │     │   django    │
│ PostgreSQL  │◀────│    Redis    │◀────│   API       │
│   :5432     │     │   :6379     │     │   :8000     │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                    ┌──────┴──────┐             │ (profile: celery)
                    │ (realtime)  │             ▼
                    ▼             │      ┌─────────────┐     ┌─────────────┐
             ┌─────────────┐     │      │celery-worker│     │ celery-beat │
             │ centrifugo  │     │      │  (Tasks)    │     │ (Scheduler) │
             │  :8800      │     │      └─────────────┘     └─────────────┘
             └─────────────┘     │             │
                                 │             │ (profile: monitoring)
                                 │             ▼
                                 │      ┌─────────────┐
                                 │      │   flower    │
                                 │      │   :5555     │
                                 │      └─────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       docker-compose.prod.yml (Production)                  │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │   nginx     │
        ┌──────────▶│   :80/443   │◀──────────┐
        │           └──────┬──────┘           │
        │              /   │   /centrifugo/   │
        │             ▼    │         ▼        │
┌───────┴───────┐ ┌────────┴────┐ ┌───────────┴───┐
│    static     │ │   django    │ │  centrifugo   │
│    files      │ │   :8000     │ │  (WebSocket)  │
└───────────────┘ └──────┬──────┘ └───────┬───────┘
                         │                │
            ┌────────────┼────────────┐   │
            ▼            ▼            ▼   │
     ┌───────────┐ ┌───────────┐ ┌────────┴──┐
     │    db     │ │   redis   │ │  celery   │
     │ PostgreSQL│ │   Redis   │ │  workers  │
     └───────────┘ └───────────┘ └───────────┘
```

### Dockerfile Variants

| Dockerfile | Use Case | Base Image | Size | Features |
|------------|----------|------------|------|----------|
| `Dockerfile` | Production | python:3.13-slim | ~250MB | Multi-stage, health checks, security |
| `Dockerfile.uv` | CI/CD | uv:python3.13 | ~200MB | Fast builds, UV native |
| `deploy/docker/Dockerfile.single` | PaaS | python:3.13-slim | ~250MB | Single container, health checks |

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────┐          ┌─────────────────────┐
│       User          │          │        Todo         │
├─────────────────────┤          ├─────────────────────┤
│ PK  id (UUID)       │──────────│ PK  id (UUID)       │
│     email           │          │ FK  user_id         │
│     username        │          │     title           │
│     password_hash   │          │     description     │
│     first_name      │          │     completed       │
│     last_name       │          │     priority        │
│     is_active       │          │     is_active       │
│     is_staff        │          │     deleted_at      │
│     is_verified     │          │ FK  created_by      │
│     metadata (JSON) │          │ FK  updated_by      │
│     created_at      │          │ FK  deleted_by      │
│     updated_at      │          │     metadata (JSON) │
└─────────────────────┘          │     created_at      │
         │                       │     updated_at      │
         │ 1:N                   └─────────────────────┘
         ▼
┌─────────────────────┐
│        OTP          │
├─────────────────────┤
│ PK  id (UUID)       │
│ FK  user_id         │
│     code            │
│     token           │
│     purpose         │
│     delivery_method │
│     expires_at      │
│     is_used         │
│     attempts        │
│     max_attempts    │
│     created_at      │
└─────────────────────┘
```

---

## API Design

### Endpoint Structure

```
/api/
├── /health/                    # Health check
│   └── GET                     # → HealthResponse
│
├── /auth/                      # Authentication
│   ├── /login/                 # POST → TokenResponse
│   ├── /logout/                # POST → MessageResponse
│   ├── /register/              # POST → UserResponse
│   ├── /refresh/               # POST → TokenResponse
│   └── /otp/                   # OTP Authentication
│       ├── /request/           # POST → OTPResponse
│       └── /verify/            # POST → TokenResponse
│
├── /users/                     # User Management
│   ├── GET                     # List users (admin)
│   ├── /me/                    # GET → Current user
│   └── /{id}/                  # GET/PUT/DELETE
│
├── /realtime/                  # Centrifugo Real-Time
│   ├── /connection-token/      # POST → ConnectionTokenResponse
│   └── /subscription-token/    # POST → SubscriptionTokenResponse
│
└── /todos/                     # Example Resource
    ├── GET                     # List (paginated)
    ├── POST                    # Create
    └── /{id}/
        ├── GET                 # Retrieve
        ├── PUT                 # Update
        └── DELETE              # Delete
```

### Response Patterns

```python
# Success Response
{
    "items": [...],           # For lists
    "meta": {                 # Pagination metadata
        "current_page": 1,
        "per_page": 20,
        "total_items": 100,
        "total_pages": 5
    }
}

# Error Response
{
    "error": "Error message",
    "code": "ERROR_CODE",
    "details": {...}          # Optional
}
```

---

## Authentication Flow

### JWT Authentication

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client  │                    │   API    │                    │    DB    │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  POST /auth/login             │                               │
     │  {email, password}            │                               │
     │──────────────────────────────▶│                               │
     │                               │  Verify credentials           │
     │                               │──────────────────────────────▶│
     │                               │◀──────────────────────────────│
     │                               │                               │
     │  {access_token, refresh}      │  Generate JWT                 │
     │◀──────────────────────────────│                               │
     │                               │                               │
     │  GET /api/resource            │                               │
     │  Authorization: Bearer {jwt}  │                               │
     │──────────────────────────────▶│                               │
     │                               │  Validate JWT                 │
     │                               │  Extract user_id              │
     │                               │──────────────────────────────▶│
     │  {data}                       │◀──────────────────────────────│
     │◀──────────────────────────────│                               │
     │                               │                               │
```

### OTP/Magic Link Flow

```
┌──────────┐                    ┌──────────┐         ┌──────────┐  ┌──────────┐
│  Client  │                    │   API    │         │  Redis   │  │  Email   │
└────┬─────┘                    └────┬─────┘         └────┬─────┘  └────┬─────┘
     │                               │                    │             │
     │  POST /auth/otp/request       │                    │             │
     │  {email}                      │                    │             │
     │──────────────────────────────▶│                    │             │
     │                               │  Generate OTP      │             │
     │                               │  Store with TTL    │             │
     │                               │───────────────────▶│             │
     │                               │                    │             │
     │                               │  Send OTP email    │             │
     │                               │────────────────────┼────────────▶│
     │  {success: true}              │                    │             │
     │◀──────────────────────────────│                    │             │
     │                               │                    │             │
     │  POST /auth/otp/verify        │                    │             │
     │  {email, code}                │                    │             │
     │──────────────────────────────▶│                    │             │
     │                               │  Verify OTP        │             │
     │                               │───────────────────▶│             │
     │                               │◀──────────────────│             │
     │  {access_token, refresh}      │                    │             │
     │◀──────────────────────────────│                    │             │
     │                               │                    │             │
```

---

## Background Tasks

### Celery Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CELERY ECOSYSTEM                               │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────────┐
     │   Django API    │
     │   (Producer)    │
     └────────┬────────┘
              │
              │ task.delay()
              ▼
     ┌─────────────────┐
     │     Redis       │
     │  (Broker)       │──────────────────────────────┐
     │                 │                              │
     └────────┬────────┘                              │
              │                                       │
              │ consume                               │ results
              ▼                                       ▼
     ┌─────────────────┐                     ┌─────────────────┐
     │  Celery Worker  │────────────────────▶│     Redis       │
     │  (Consumer)     │     store result    │  (Result Store) │
     └─────────────────┘                     └─────────────────┘

     ┌─────────────────┐
     │  Celery Beat    │
     │  (Scheduler)    │
     │                 │
     │  • Daily tasks  │
     │  • Cleanup jobs │
     │  • Reports      │
     └─────────────────┘

     ┌─────────────────┐
     │     Flower      │
     │  (Monitoring)   │
     │                 │
     │  • Task status  │
     │  • Worker stats │
     │  • Queue depth  │
     └─────────────────┘
```

---

## Deployment Options

### Decision Tree

```
                            ┌─────────────────────┐
                            │  Choose Deployment  │
                            └──────────┬──────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Simple?    │   │   Managed?   │   │  Enterprise? │
            │ (1-2 devs)   │   │ (PaaS)       │   │ (K8s)        │
            └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                   │                  │                  │
                   ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Docker     │   │   Railway    │   │  Kubernetes  │
            │   Compose    │   │   Render     │   │    Helm      │
            │              │   │   Fly.io     │   │              │
            └──────────────┘   └──────────────┘   └──────────────┘
```

### Deployment Comparison

| Feature | Docker Compose | PaaS | Kubernetes |
|---------|---------------|------|------------|
| **Complexity** | Low | Low | High |
| **Scaling** | Manual | Auto | Auto |
| **Cost** | Fixed server | Pay-per-use | Variable |
| **Control** | Full | Limited | Full |
| **Setup Time** | Minutes | Minutes | Hours |
| **Best For** | Dev/Small prod | Startups | Enterprise |

### Kubernetes Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KUBERNETES CLUSTER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        INGRESS CONTROLLER                           │   │
│  │                    (nginx-ingress / traefik)                        │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                         │
│                                  ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                            SERVICE                                   │   │
│  │                    django-ninja-stack-app                           │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                         │
│         ┌────────────────────────┼────────────────────────┐               │
│         ▼                        ▼                        ▼               │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐       │
│  │  Django     │          │  Django     │          │  Django     │       │
│  │  Pod 1      │          │  Pod 2      │          │  Pod N      │       │
│  │             │          │             │          │             │       │
│  │ ┌─────────┐ │          │ ┌─────────┐ │          │ ┌─────────┐ │       │
│  │ │Container│ │          │ │Container│ │          │ │Container│ │       │
│  │ └─────────┘ │          │ └─────────┘ │          │ └─────────┘ │       │
│  └─────────────┘          └─────────────┘          └─────────────┘       │
│                                  │                                         │
│                                  ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        HPA (Autoscaler)                             │   │
│  │               min: 2 replicas, max: 10 replicas                     │   │
│  │               CPU target: 70%, Memory target: 80%                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │    PostgreSQL   │     │      Redis      │     │  Celery Worker  │       │
│  │   (StatefulSet) │     │   (StatefulSet) │     │   (Deployment)  │       │
│  │                 │     │                 │     │                 │       │
│  │  • PVC storage  │     │  • PVC storage  │     │  • Replicas: 3  │       │
│  │  • Secrets      │     │  • Secrets      │     │  • Resources    │       │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Performance Considerations

### Gunicorn Worker Configuration

```
Workers = (2 × CPU cores) + 1

Example for 4-core server:
  Workers = (2 × 4) + 1 = 9

With threads (gthread worker class):
  Workers = CPU cores
  Threads per worker = 2-4

Memory per worker: ~50-100MB
Total memory = Workers × Memory per worker
```

### Caching Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CACHING LAYERS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────────┐
     │   Client        │
     │  (Browser)      │───────▶  HTTP Cache Headers
     └─────────────────┘          • ETag
                                  • Cache-Control
                                  • Last-Modified
            │
            ▼
     ┌─────────────────┐
     │      CDN        │───────▶  Static Assets
     │  (CloudFlare)   │          • CSS, JS, Images
     └─────────────────┘          • TTL: 1 year
            │
            ▼
     ┌─────────────────┐
     │     Nginx       │───────▶  Proxy Cache
     │                 │          • API responses
     └─────────────────┘          • TTL: varies
            │
            ▼
     ┌─────────────────┐
     │     Redis       │───────▶  Application Cache
     │                 │          • Sessions
     └─────────────────┘          • Rate limits
                                  • Query results
            │
            ▼
     ┌─────────────────┐
     │   PostgreSQL    │───────▶  Query Cache
     │                 │          • Prepared statements
     └─────────────────┘          • Connection pooling
```

---

## Security Architecture

### Security Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SECURITY LAYERS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

     Layer 1: Network
     ┌─────────────────────────────────────────────────────────────────────┐
     │  • TLS/HTTPS only                                                   │
     │  • Firewall rules                                                   │
     │  • VPC/Private networks                                             │
     └─────────────────────────────────────────────────────────────────────┘

     Layer 2: Application
     ┌─────────────────────────────────────────────────────────────────────┐
     │  • Rate limiting (api/throttling/)                                  │
     │  • Input validation (Pydantic schemas)                              │
     │  • CORS configuration                                               │
     │  • Security headers (X-Frame-Options, CSP, etc.)                    │
     └─────────────────────────────────────────────────────────────────────┘

     Layer 3: Authentication
     ┌─────────────────────────────────────────────────────────────────────┐
     │  • JWT with short expiry (15 min)                                   │
     │  • Refresh token rotation                                           │
     │  • Password hashing (bcrypt)                                        │
     │  • OTP/2FA support                                                  │
     └─────────────────────────────────────────────────────────────────────┘

     Layer 4: Container
     ┌─────────────────────────────────────────────────────────────────────┐
     │  • Non-root user                                                    │
     │  • Read-only filesystem (where possible)                            │
     │  • Minimal base image (slim variants)                               │
     │  • No unnecessary packages                                          │
     └─────────────────────────────────────────────────────────────────────┘
```

---

## Monitoring & Observability

### Observability Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OBSERVABILITY STACK                                 │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────────────────────────────────────────────────────────────┐
     │                        DJANGO APPLICATION                           │
     │                                                                     │
     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
     │  │  Tracing    │  │   Metrics   │  │  Logging    │  │  Health   │  │
     │  │ (OTel SDK)  │  │ (Prometheus)│  │ (Structured)│  │  Checks   │  │
     │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
     └─────────┼────────────────┼────────────────┼────────────────┼────────┘
               │                │                │                │
               ▼                ▼                ▼                ▼
     ┌─────────────────┐  ┌───────────┐  ┌─────────────┐  ┌───────────────┐
     │     Jaeger      │  │  /metrics │  │   stdout    │  │ /api/health/  │
     │  (Trace UI)     │  │  endpoint │  │   (JSON)    │  │   detailed    │
     │   :16686        │  │           │  │             │  │               │
     └─────────────────┘  └───────────┘  └─────────────┘  └───────────────┘
```

### Trace Propagation

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  Django  │────▶│  Celery  │────▶│ External │
│ Request  │     │   API    │     │  Worker  │     │   API    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                │                │
     │ trace-id: abc  │ trace-id: abc  │ trace-id: abc  │ trace-id: abc
     │ span-id: 001   │ span-id: 002   │ span-id: 003   │ span-id: 004
     └────────────────┴────────────────┴────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Jaeger    │
                    │  Timeline   │
                    │             │
                    │  abc-001 ───┤
                    │    abc-002 ─┤
                    │      abc-003┤
                    │        abc-004
                    └─────────────┘
```

### Audit Trail Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUDIT LOGGING SYSTEM                               │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────────┐
     │   API Request   │
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐     ┌─────────────────┐
     │    Middleware   │────▶│   AuditLog      │
     │ (Request/Resp)  │     │    (CREATE)     │
     └─────────────────┘     └─────────────────┘
              │
              ▼
     ┌─────────────────┐     ┌─────────────────┐
     │    Signals      │────▶│   AuditLog      │
     │ (Model Changes) │     │ (UPDATE/DELETE) │
     └─────────────────┘     └─────────────────┘
              │
              ▼
     ┌─────────────────┐     ┌─────────────────┐
     │   Decorators    │────▶│   AuditLog      │
     │  (@audit_action)│     │   (CUSTOM)      │
     └─────────────────┘     └─────────────────┘

     ┌─────────────────────────────────────────────────────────────────────┐
     │                      AUDIT LOG ENTRY                                │
     │                                                                     │
     │  • action: CREATE | UPDATE | DELETE | LOGIN | CUSTOM                │
     │  • user: preserved email even after deletion                        │
     │  • ip_address: client IP (proxy-aware)                              │
     │  • model_name: affected model                                       │
     │  • object_id: affected record                                       │
     │  • changes: { "field": {"old": "x", "new": "y"} }                  │
     │  • request_id: correlation ID                                       │
     │  • timestamp: immutable                                             │
     └─────────────────────────────────────────────────────────────────────┘
```

### Feature Flags Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FEATURE FLAGS SYSTEM                                │
└─────────────────────────────────────────────────────────────────────────────┘

     Request Flow:
     ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
     │  Client  │────▶│  Middleware  │────▶│   Service    │────▶│   View   │
     └──────────┘     └──────────────┘     └──────────────┘     └──────────┘
                             │                    │
                             ▼                    ▼
                      request.feature_flags  is_enabled()
                                            get_variant()

     Flag Types:
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │    BOOLEAN      │     │   PERCENTAGE    │     │    AB_TEST      │
     │                 │     │                 │     │                 │
     │  enabled: true  │     │  rollout: 25%   │     │  control: 50%   │
     │  or false       │     │  (user hash)    │     │  variant_a: 30% │
     │                 │     │                 │     │  variant_b: 20% │
     └─────────────────┘     └─────────────────┘     └─────────────────┘

     Targeting:
     ┌─────────────────────────────────────────────────────────────────────┐
     │  • User whitelist/blacklist                                        │
     │  • Environment targeting (dev, staging, prod)                      │
     │  • Time-based activation (starts_at, ends_at)                      │
     │  • Custom conditions (user attributes, context)                    │
     └─────────────────────────────────────────────────────────────────────┘
```

### Metrics & Logging (External Tools)

```
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │     Django      │     │     Celery      │     │     Nginx       │
     │     Logs        │     │     Logs        │     │     Logs        │
     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │   Log Collector │
                             │  (Fluentd/etc)  │
                             └────────┬────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │  Elasticsearch  │     │   Prometheus    │     │     Sentry      │
     │    (Logs)       │     │   (Metrics)     │     │   (Errors)      │
     └────────┬────────┘     └────────┬────────┘     └─────────────────┘
              │                       │
              ▼                       ▼
     ┌─────────────────┐     ┌─────────────────┐
     │     Kibana      │     │    Grafana      │
     │  (Log Viewer)   │     │  (Dashboards)   │
     └─────────────────┘     └─────────────────┘
```

---

## Quick Reference

### Common Commands

```bash
# Development
make setup          # One-command setup
make dev            # Start development server
make test           # Run tests
make lint           # Check code quality

# Docker
make up             # Start all services
make up-realtime    # Start with Centrifugo
make down           # Stop all services
make logs           # View logs
make shell          # Django shell

# Database
make migrate        # Run migrations
make backup         # Backup database

# Celery
make celery         # Start with Celery
make flower         # Start with Flower monitoring
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Debug mode | `False` |
| `SECRET_KEY` | Django secret | Required |
| `DATABASE_URL` | PostgreSQL URL | Required |
| `REDIS_URL` | Redis URL | Required |
| `ALLOWED_HOSTS` | Allowed hosts | `localhost` |
| `CENTRIFUGO_URL` | Centrifugo server URL | `http://centrifugo:8000` |
| `CENTRIFUGO_API_KEY` | Centrifugo API key | Required (prod) |
| `CENTRIFUGO_TOKEN_SECRET` | JWT signing secret | Required (prod) |

---

*Last updated: February 2026*
