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

```mermaid
graph TB
    subgraph Clients["Client Applications"]
        Web["Web"]
        Mobile["Mobile"]
        IoT["IoT"]
        ThirdParty["Third-party Services"]
    end

    LB["Load Balancer / CDN<br/>(Nginx, CloudFlare, AWS ALB)"]

    subgraph API["Django API Cluster"]
        API1["Django API Instance 1<br/>(Gunicorn)"]
        API2["Django API Instance 2<br/>(Gunicorn)"]
        APIN["Django API Instance N<br/>(Gunicorn)"]
    end

    PG[("PostgreSQL<br/>Primary DB")]
    Redis[("Valkey<br/>Cache / Broker")]
    Celery["Celery Workers"]

    Clients --> LB --> API
    API1 & API2 & APIN --> PG
    API1 & API2 & APIN --> Redis
    API1 & API2 & APIN --> Celery
```

### Component Summary

| Component | Purpose | Technology |
|-----------|---------|------------|
| **API Server** | REST API endpoints | Django Ninja + Gunicorn |
| **Database** | Persistent data storage | PostgreSQL 17 |
| **Cache/Broker** | Caching & message queue | Valkey 8 (Redis-compatible) |
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
│   ├── utils/                   # HTTP utilities, HTTP client
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
│   │   ├── users_controller.py  # User management
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

```mermaid
sequenceDiagram
    participant C as Client
    participant N as Nginx Proxy
    participant G as Gunicorn Worker
    participant M as Django Middleware
    participant V as Controller (View)
    participant S as Service Layer
    participant DB as Database / Cache

    C->>N: HTTP Request
    N->>G: Forward
    G->>M: Process request
    M->>V: Route to controller
    V->>S: Delegate logic
    S->>DB: Query / Mutate
    DB-->>S: Result
    S-->>V: Domain object
    V-->>M: HTTP Response
    M-->>G: Process response
    G-->>N: Forward
    N-->>C: HTTP Response
```

### Layer Responsibilities

```mermaid
graph TB
    subgraph Presentation["Presentation Layer"]
        Controllers["Controllers<br/>(API Routes)"]
        Schemas["Schemas<br/>(Validation)"]
        Decorators["Decorators<br/>(Auth/Logging)"]
    end

    subgraph Business["Business Layer"]
        Services["Services<br/>(Business Logic)"]
        Validators["Validators<br/>(Domain Rules)"]
        Utils["Utils<br/>(Helpers)"]
    end

    subgraph Data["Data Layer"]
        Models["Models<br/>(ORM Entities)"]
        Managers["Managers<br/>(Custom Queries)"]
        QuerySets["QuerySets<br/>(Filtering)"]
    end

    Presentation --> Business --> Data
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

```mermaid
graph TB
    REQ["HTTP Request"]

    subgraph Controller["Controller Layer (HTTP concerns only)"]
        D["Declarative<br/>(try/except)"]
        B["Basic<br/>(get_or_404)"]
        P["Partial<br/>(selective decorators)"]
        F["Full — @handle_exceptions + @log_api_call + service<br/>↓ delegates all logic to TodoService"]
    end

    subgraph Service["Service Layer — todos/services/todo_service.py"]
        TS["TodoService<br/>├── list_todos(user, search, completed, priority, ordering)<br/>├── get_todo(todo_id, user) → Todo | Http404<br/>├── create_todo(payload, user) → Todo<br/>├── update_todo(todo_id, payload, user) → Todo | Http404<br/>├── delete_todo(todo_id, user) → None | Http404<br/>├── list_completed_todos(user) → QuerySet<br/>├── list_pending_todos(user) → QuerySet<br/>└── search_todos(user, q, priority, completed) → QuerySet"]
    end

    subgraph DataLayer["Data Layer — todos/models/todo.py (ORM)"]
        ORM["Django ORM"]
    end

    REQ --> Controller
    D & B & P -.->|hit DB directly| ORM
    F -->|Pattern 4 only| Service --> ORM
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

```mermaid
graph TB
    REQ["HTTP POST /todos/"]
    LOG["@log_api_call<br/>logs request start/end, payload, duration"]
    EXC["@handle_exceptions<br/>catches exceptions → structured 500 response"]
    VAL["@validate_request<br/>runs extra schema validation before handler"]
    HANDLER["def create_todo()<br/>thin handler, delegates to service"]
    SVC["TodoService.create_todo()<br/>business logic, ORM calls"]

    REQ --> LOG --> EXC --> VAL --> HANDLER --> SVC
```

---

## Docker Architecture

### Multi-Stage Build Process

```mermaid
graph TB
    subgraph Stage1["Stage 1: Builder (~800MB)"]
        S1["python:3.13-slim<br/>• Install build tools (gcc, build-essential)<br/>• Install uv package manager<br/>• Create virtual environment<br/>• Install Python dependencies"]
    end

    subgraph Stage2["Stage 2: Production (~250MB)"]
        S2["python:3.13-slim<br/>• Runtime libraries only (libpq5, curl)<br/>• Virtual environment from builder<br/>• Application code<br/>• Non-root user (security)<br/>• Health checks"]
    end

    Stage1 -->|"COPY /opt/venv"| Stage2
```

### Docker Compose Services

```mermaid
graph TB
    subgraph Dev["docker-compose.yml (Development)"]
        DB[("PostgreSQL<br/>:5432")]
        REDIS[("Valkey<br/>:6379")]
        DJANGO["Django API<br/>:8000"]
        CENT["Centrifugo<br/>:8800<br/>(realtime profile)"]
        WORKER["Celery Worker<br/>(celery profile)"]
        BEAT["Celery Beat<br/>(celery profile)"]
        FLOWER["Flower<br/>:5555<br/>(monitoring profile)"]

        DJANGO --> DB
        DJANGO --> REDIS
        WORKER --> REDIS
        BEAT --> REDIS
        FLOWER --> REDIS
        CENT --> REDIS
    end

    subgraph Prod["docker-compose.prod.yml (Production)"]
        NGINX["Nginx<br/>:80/443"]
        DJPROD["Django<br/>:8000"]
        CENTPROD["Centrifugo<br/>(WebSocket)"]
        STATIC["Static Files"]
        DBPROD[("PostgreSQL")]
        REDPROD[("Valkey")]
        CELPROD["Celery Workers"]

        NGINX -->|"/api/"| DJPROD
        NGINX -->|"/centrifugo/"| CENTPROD
        NGINX -->|"/static/"| STATIC
        DJPROD --> DBPROD & REDPROD & CELPROD
    end
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

```mermaid
erDiagram
    User {
        UUID id PK
        string email
        string username
        string password_hash
        string first_name
        string last_name
        boolean is_active
        boolean is_staff
        boolean is_verified
        json metadata
        datetime created_at
        datetime updated_at
    }

    Todo {
        UUID id PK
        UUID user_id FK
        string title
        text description
        boolean completed
        string priority
        boolean is_active
        datetime deleted_at
        UUID created_by FK
        UUID updated_by FK
        UUID deleted_by FK
        json metadata
        datetime created_at
        datetime updated_at
    }

    OTP {
        UUID id PK
        UUID user_id FK
        string code
        string token
        string purpose
        string delivery_method
        datetime expires_at
        boolean is_used
        int attempts
        int max_attempts
        datetime created_at
    }

    User ||--o{ Todo : "has many"
    User ||--o{ OTP : "has many"
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

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API
    participant DB as Database

    C->>API: POST /auth/login {email, password}
    API->>DB: Verify credentials
    DB-->>API: User found
    API-->>C: {access_token, refresh_token}

    C->>API: GET /api/resource<br/>Authorization: Bearer {jwt}
    API->>API: Validate JWT, extract user_id
    API->>DB: Fetch data
    DB-->>API: Data
    API-->>C: {data}
```

### OTP / Magic Link Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API
    participant R as Valkey
    participant E as Email Service

    C->>API: POST /auth/otp/request {email}
    API->>R: Generate & store OTP with TTL
    API->>E: Send OTP email
    API-->>C: {success: true}

    C->>API: POST /auth/otp/verify {email, code}
    API->>R: Verify OTP
    R-->>API: Valid
    API-->>C: {access_token, refresh_token}
```

---

## Background Tasks

### Celery Architecture

```mermaid
graph TB
    subgraph Producers
        DJANGO["Django API<br/>(Producer)"]
    end

    BROKER[("Valkey<br/>Broker")]
    RESULTS[("Valkey<br/>Result Store")]

    subgraph Workers
        WORKER["Celery Worker<br/>(Consumer)"]
    end

    BEAT["Celery Beat<br/>(Scheduler)<br/>• Daily tasks<br/>• Cleanup jobs<br/>• Reports"]

    FLOWER["Flower<br/>(Monitoring)<br/>• Task status<br/>• Worker stats<br/>• Queue depth"]

    DJANGO -->|"task.delay()"| BROKER
    BROKER -->|"consume"| WORKER
    WORKER -->|"store result"| RESULTS
    BEAT -->|"schedule"| BROKER
    FLOWER -.->|"monitor"| BROKER
```

---

## Deployment Options

### Decision Tree

```mermaid
graph TB
    START["Choose Deployment"]

    SIMPLE["Simple?<br/>(1-2 devs)"]
    MANAGED["Managed?<br/>(PaaS)"]
    ENTERPRISE["Enterprise?<br/>(K8s)"]

    DOCKER["Docker Compose"]
    PAAS["Railway<br/>Render<br/>Fly.io"]
    K8S["Kubernetes<br/>Helm"]

    START --> SIMPLE & MANAGED & ENTERPRISE
    SIMPLE --> DOCKER
    MANAGED --> PAAS
    ENTERPRISE --> K8S
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

```mermaid
graph TB
    subgraph K8S["Kubernetes Cluster"]
        INGRESS["Ingress Controller<br/>(nginx-ingress / traefik)"]

        SVC["Service<br/>django-ninja-stack-app"]

        subgraph Pods["Django Pods"]
            P1["Pod 1"]
            P2["Pod 2"]
            PN["Pod N"]
        end

        HPA["HPA (Autoscaler)<br/>min: 2, max: 10 replicas<br/>CPU: 70%, Memory: 80%"]

        PG[("PostgreSQL<br/>StatefulSet<br/>• PVC storage<br/>• Secrets")]
        REDIS[("Valkey<br/>StatefulSet<br/>• PVC storage<br/>• Secrets")]
        CELERY["Celery Worker<br/>Deployment<br/>• Replicas: 3<br/>• Resources"]
    end

    INGRESS --> SVC --> Pods
    HPA -.->|"scale"| Pods
    P1 & P2 & PN --> PG & REDIS
    CELERY --> REDIS
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
