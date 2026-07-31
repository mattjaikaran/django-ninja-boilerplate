# Django Ninja Boilerplate — Roadmap

> Generated: 2026-07-31 | Current: v1.8.0
>
> This document captures planned enhancements across version milestones.
> No implementation has begun — this is a planning artifact only.

---

| Version | Theme | Scope |
|---------|-------|-------|
| **1.9.0** | Admin & Operational Foundation | Unfold dashboards, DLQ UI, import/export, scheduled jobs UI |
| **1.10.0** | Observability Deepening | Operational dashboards, request log browser, alerting, rate limit visibility |
| **1.11.0** | API Maturity Patterns | Batch operations, long-running ops, full-text search, event bus foundation |
| **2.0.0** | Platform Scale | ETL framework, production SDKs, Django 6.0+, Postgres 19, multi-DB, multi-tenancy, GDPR |
| **2.1.0** | AI & Intelligent Features | LLM integration patterns, streaming AI, RAG pipelines, AI-powered admin, content moderation |
| **2.2.0** | Multi-Protocol & Advanced Auth | gRPC endpoints, GraphQL subscriptions, OAuth2/SAML SSO, API mock server |
| **2.3.0** | Infrastructure & Operations | i18n, distributed locking, IaC modules, K8s operator, data catalog, scheduled reports |
| **3.0.0** | Multi-Service Architecture | Service decomposition, event sourcing/CQRS, saga patterns, service mesh, contract testing |

---

## v1.9.0 — Admin & Operational Foundation

**Theme**: Make the Django Unfold admin a genuine operations cockpit.
These are the highest-value, lowest-risk additions — all leverage existing infrastructure.

### Admin Dashboard Pages

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 1.1 | **System Health Dashboard** | P0 | Surface `core/observability/health.py` checks in Unfold admin. Color-coded cards for DB, Valkey, Celery, Centrifugo, disk, memory. Auto-refresh via HTMX or polling. |
| 1.2 | **Metrics Overview Page** | P0 | Prometheus counters/gauges/histograms rendered as Unfold dashboard widgets. Request rate, error rate, p50/p95/p99 latency, active users, cache hit rate. |
| 1.3 | **Celery Job Monitor** | P0 | Admin page showing active/scheduled/failed tasks, queue depths, worker heartbeats. Retry/revoke actions. Reduces need to open Flower separately. |
| 1.4 | **API Key Usage Dashboard** | P1 | Last-used timestamps, key age, top consumers by request count, revoked key audit. |

### Admin Enhancement — Operations

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 1.5 | **django-import-export Wiring** | P0 | Wire `django-import-export` (already installed) into all admin models: Users, API Keys, Audit Logs, Plans, Subscriptions, Webhooks, Notifications. Export to CSV/JSON/Excel. |
| 1.6 | **Dead Letter Queue Admin UI** | P0 | Inspect, filter, retry, or discard dead-lettered tasks from `core/tasks/dlq.py`. Show failure reason, attempt count, original args. |
| 1.7 | **Scheduled Jobs Admin UI** | P0 | Register `django-celery-beat` models (PeriodicTask, CrontabSchedule, IntervalSchedule) in Unfold admin so operators can view/edit schedules without shell. |
| 1.8 | **Bulk Admin Actions** | P1 | Unfold actions: bulk-verify emails, bulk-revoke API keys, bulk-send notifications, bulk-activate/deactivate users. |
| 1.9 | **Soft-Delete Filtering** | P2 | Changelist filters for `is_active` (soft-deleted records) across all models using `SoftDeleteModel`. Default to hiding deleted records. |

### Admin Enhancement — Audit & Security

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 1.10 | **Audit Log Date Range Export** | P1 | Add date-range picker + export action to AuditLog admin. Useful for compliance audits. |
| 1.11 | **Login Attempt Monitor** | P2 | Admin view showing failed login attempts by IP/user, brute-force indicators, account lockout status. |

---

## v1.10.0 — Observability Deepening

**Theme**: Make observability self-serve. Operators shouldn't need Grafana/Jaeger/Flower for routine questions.

### Operational Dashboard

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 2.1 | **Request Analytics Dashboard** | P0 | Top-N endpoints by calls, status code distribution, error rate trends, slowest endpoints. Data from `ObservabilityMiddleware` metrics. |
| 2.2 | **Database Stats Dashboard** | P0 | Query count trends, slow query log viewer (from PostgreSQL `pg_stat_statements`), connection pool utilization. |
| 2.3 | **Cache Analytics Dashboard** | P1 | Valkey hit/miss rates, key counts, eviction stats, memory usage. |
| 2.4 | **Celery Throughput Dashboard** | P0 | Tasks/sec, queue depth trends, failure rates by task type, worker heartbeat timeline. |

### Request Log Browser

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 2.5 | **Request/Response Log Browser** | P0 | Admin page browsing recent API requests from `ObservabilityMiddleware`. Filter by status code, method, endpoint, user, slow requests (>N ms). Clickable trace IDs. |
| 2.6 | **Trace ID Lookup** | P1 | Given a trace ID, show the full span waterfall across Django → Celery → DB → external calls. |

### Alerting

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 2.7 | **Alert Rule Configuration** | P0 | Define thresholds in admin: error rate > X%, p95 latency > Y ms, disk > Z%, Celery queue depth > N. |
| 2.8 | **Notification Channels** | P0 | Slack webhook, Discord webhook, email. Reuse existing notification infrastructure. |
| 2.9 | **Alert History & Acknowledgments** | P1 | Alert firing history, acknowledged-by tracking, mute/unmute controls. |

### Rate Limiting

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 2.10 | **Rate Limit Dashboard** | P0 | Per-endpoint throttle configuration, hit counters, blocked clients. Client IP/API-key throttle status. |
| 2.11 | **Dynamic Rate Limit Adjustment** | P2 | Adjust throttle rates in admin without code deploy. |

---

## v1.11.0 — API Maturity Patterns

**Theme**: Production API patterns that real applications need — batch operations, async workflows, search, events.

### Batch & Bulk Operations

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 3.1 | **BulkAPIMixin** | P0 | Mixin for controllers: `bulk_create`, `bulk_update`, `bulk_delete`. Partial-failure reporting (which items succeeded/failed). Configurable batch size limits. |
| 3.2 | **Bulk Operation Schema** | P0 | Standard request/response shapes: `BulkCreateRequest[T]`, `BulkUpdateRequest[T]`, `BulkResult[T]` with per-item status. |

### Long-Running Operations

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 3.3 | **AsyncOperation Model & Pattern** | P0 | Model: `operation_id, type, status, progress_pct, result, error, created_by, created_at`. Controller starts Celery task → 202 + `operation_id`. Client polls `GET /operations/{id}`. |
| 3.4 | **Operation Admin Dashboard** | P0 | Admin page showing all operations, filterable by status/type/user. Cancel stuck operations. |
| 3.5 | **Operation Progress WebSocket** | P2 | Push progress updates via Centrifugo instead of polling. Subscribe to `operations:<user_id>`. |

### Full-Text Search

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 3.6 | **PostgreSQL Full-Text Search** | P0 | `SearchableModel` mixin: auto-generates `SearchVectorField`, `SearchQuery`-based `search()` queryset method. Weighted fields (title > description). No additional infra needed. |
| 3.7 | **Search API Pattern** | P0 | Standardized search endpoint pattern: `GET /api/{resource}/search?q=...&language=en&highlight=true`. Ranked results with snippets. |
| 3.8 | **Meilisearch/Typesense Adapter** | P2 | Optional adapter for larger scale. Model mixin auto-syncs on save/delete. |

### Event Bus (Internal)

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 3.9 | **Typed Event Classes** | P0 | `core/events/` — `UserRegistered`, `TodoCompleted`, `SubscriptionCreated`, etc. Strongly typed payloads via Pydantic. |
| 3.10 | **Sync + Async Dispatchers** | P0 | In-process dispatcher for sync handlers (logging, cache invalidation). Celery dispatcher for async handlers (email, webhooks, notifications). |
| 3.11 | **Event → Webhook Bridge** | P0 | Register events → auto-fire matching webhooks. Uses existing `webhooks` app delivery infrastructure. |
| 3.12 | **Event History in Audit Log** | P1 | Optionally record events in the audit log with event type, payload, dispatcher trail. |

### Pagination & Filtering

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 3.13 | **Standardized Filter Schema** | P1 | Reusable filter patterns across controllers: date ranges, multi-select enums, nested filters. |
| 3.14 | **Cursor Pagination for Feeds** | P2 | Cursor-based pagination for real-time feeds (notifications, activity streams). Already have cursor pagination utilities — wire into controller patterns. |

---

## v2.0.0 — Platform Scale

**Theme**: The boilerplate graduates from "startup-ready" to "scale-ready". ETL, production SDKs, multi-tenancy, broader database support, and Django 6.0 compatibility.

### ETL Framework

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.1 | **`etl/` App Scaffold** | P0 | New app with `Extractor`, `Transformer`, `Loader` base classes. `Pipeline` orchestrator chains E→T→L with progress tracking. Celery-backed execution. |
| 4.2 | **CSV Extractor** | P0 | Streaming CSV reader with column mapping, type coercion, validation. Chunked processing for large files. |
| 4.3 | **JSON/API Extractor** | P0 | Paginated JSON API ingestion. Configurable pagination style (page, cursor, offset-limit). Rate-limit-aware. |
| 4.4 | **PostgreSQL Cross-DB Extractor** | P1 | Read from external PostgreSQL databases via Django's multi-DB. Incremental sync via cursor column. |
| 4.5 | **S3/GCS Extractor** | P1 | Read files from S3 or GCS buckets. Support for CSV, JSON, Parquet. |
| 4.6 | **Django Bulk Loader** | P0 | `bulk_create` with configurable batch size, progress callback. Skip/update on duplicate. |
| 4.7 | **Upsert Loader** | P0 | PostgreSQL `INSERT ... ON CONFLICT` upsert. Conflict target + update columns configurable. |
| 4.8 | **Webhook/API Loader** | P1 | POST transformed data to external APIs. Retry with backoff. |
| 4.9 | **Pipeline Run Tracking** | P0 | Model tracking each pipeline run: status, row counts (extracted/transformed/loaded/errored), start/end time, error log. Admin dashboard. |
| 4.10 | **ETL Admin Dashboard** | P0 | List pipeline definitions, view run history, trigger manual runs, view error details, download error rows. |
| 4.11 | **Scheduled Pipeline Runs** | P1 | Wire ETL pipelines into Celery Beat for periodic syncs. Admin UI to configure schedules. |
| 4.12 | **CDC / Change Data Capture Hooks** | P2 | PostgreSQL logical replication listener → publish model changes as events. Bridge to webhooks. |

### Production SDK Generation

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.13 | **openapi-generator-cli Integration** | P0 | Replace/supplement template-based SDK with `openapi-generator-cli` (Java-based, industry standard). Generates idiomatic clients with proper error handling, retries, pagination. |
| 4.14 | **TypeScript SDK v2** | P0 | Production TS SDK: typed request/response, retry with exponential backoff, pagination helpers, error discrimination. |
| 4.15 | **Python SDK v2** | P0 | Production Python SDK: async httpx client, retries, pagination, typed exceptions. |
| 4.16 | **Go SDK Target** | P1 | Generate Go client for backend-to-backend integrations. |
| 4.17 | **Kotlin SDK Target** | P1 | Generate Kotlin client for Android/native mobile. |
| 4.18 | **SDK Versioning & Changelog** | P1 | SDK version tracks API version. Auto-publish SDK changelog on API spec changes. |
| 4.19 | **Webhook Verification Library** | P0 | Lightweight Py + TS libraries for consumers to verify webhook signatures. `verify_signature(body, signature_header, secret)`. |

### Django 6.0+ & Database Support

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.20 | **Django 6.0 Compatibility** | P0 | Full test suite pass on Django 6.0. Currently blocked by `django-celery-beat<6.0`. Resolve dependency ceiling, update any deprecated APIs. |
| 4.21 | **PostgreSQL 19 Support** | P0 | Test suite + Docker Compose configs for Postgres 19. Leverage new JSON/SQL features where applicable. |
| 4.22 | **MySQL 8.4 / MariaDB Support** | P1 | Optional database backends. `TimestampedModel` compatibility (no native UUID type in MySQL). Docs for switching. |
| 4.23 | **SQLite Production Notes** | P2 | Document SQLite + Litestream pattern for single-server deployments. |
| 4.24 | **Multi-Database Configuration** | P1 | Django multi-DB config for read replicas, analytics DB, external sources. Router class for read/write splitting. |

### Multi-Tenancy Deepening

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.25 | **TenantAwareModel Base** | P0 | Abstract model that auto-filters querysets by `organization_id`. Middleware sets current tenant from request context. |
| 4.26 | **TenantAwareCache** | P1 | Cache key prefixing by tenant ID. Prevents cross-tenant cache leakage. |
| 4.27 | **TenantRateLimiter** | P1 | Per-organization rate limits. Configurable in admin. |
| 4.28 | **Organization-Scoped API Keys** | P1 | API keys bound to an organization, not just a user. Scoped to organization resources. |

### GDPR & Compliance

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.29 | **User Data Export** | P0 | `GET /api/users/me/export` — all user data as structured JSON. Includes related records across all apps. |
| 4.30 | **Account Deletion with Data Scrub** | P0 | Hard-delete or anonymize user data. Configurable retention policies per data type. |
| 4.31 | **Audit Log Retention Policies** | P1 | Auto-archive/delete audit logs older than N days. Configurable per compliance requirements. |
| 4.32 | **Consent Management** | P2 | Track user consent for marketing, analytics, third-party data sharing. Audit trail for consent changes. |

### Platform Features

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.33 | **File Processing Pipeline** | P1 | Extend `files` app: async thumbnail generation, file type validation, malware scanning hook (ClamAV), processing status tracking. |
| 4.34 | **API Client Playground in Admin** | P1 | Embedded API console in Unfold admin. Pre-authenticated with session. Quick endpoint testing without leaving admin. |
| 4.35 | **GraphQL Strawberry Enhancement** | P2 | `strawberry-graphql` is already an optional dependency. Add GraphQL admin view, subscription support via Centrifugo bridge. |
| 4.36 | **Webhook Retry Policy Config** | P1 | Configurable retry schedules per webhook (exponential backoff, max attempts, final DLQ). Currently retries exist but policy isn't per-webhook configurable. |

### CLI & Developer Experience

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 4.37 | **Feature Generator: ETL Templates** | P1 | `generate_feature etl --source csv --target postgres` |
| 4.38 | **Feature Generator: Search Templates** | P2 | `generate_feature search --backend pg_fulltext` |
| 4.39 | **Feature Generator: Dashboard Templates** | P1 | `generate_feature dashboard --type admin` |
| 4.40 | **API Changelog CI Integration** | P1 | On PR merge, compare old→new OpenAPI spec, auto-post changelog as PR comment. Version bump detection from spec diff. |

---

## v2.1.0 — AI & Intelligent Features

**Theme**: First-class AI integration patterns. As LLMs become infrastructure, the boilerplate should ship production-ready patterns for building AI features — not just calling an API, but streaming, RAG, prompt management, and AI-augmented operations.

### LLM Integration Core

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 5.1 | **LLM Provider Abstraction** | P0 | `core/ai/` — unified interface over OpenAI, Anthropic, Google, and local models. Provider-agnostic `completion()`, `chat()`, `stream()` methods. API key management via settings. |
| 5.2 | **Streaming AI Responses via SSE** | P0 | Controller pattern for streaming LLM output to clients. Reuses `core/sse/` infrastructure. Token-by-token delivery with proper backpressure. |
| 5.3 | **Prompt Management & Versioning** | P0 | `PromptTemplate` model: name, version, template text, variables, provider config. Admin UI for editing/testing prompts. API for fetching latest prompt version. |
| 5.4 | **AI Request Logging & Observability** | P1 | Log all AI calls: model, tokens in/out, latency, cost estimate. Admin dashboard for AI usage and cost tracking. |

### RAG (Retrieval-Augmented Generation)

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 5.5 | **Document Chunking Pipeline** | P0 | Ingest documents → chunk → embed → store. Configurable chunking strategies (fixed-size, sentence, recursive). |
| 5.6 | **Vector Store Integration** | P0 | pgvector extension for PostgreSQL (zero new infra). `EmbeddableModel` mixin: auto-generates and stores embeddings on save. |
| 5.7 | **Semantic Search API** | P0 | `GET /api/search/semantic?q=...&top_k=10`. Returns ranked results with relevance scores. Hybrid (full-text + vector) search option. |
| 5.8 | **RAG Query Pipeline** | P1 | End-to-end: embed query → retrieve chunks → construct prompt → call LLM → return answer with citations. |

### AI-Powered Admin Features

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 5.9 | **Anomaly Detection** | P1 | ML-based anomaly detection on request patterns, error rates, and user behavior. Alerts on unusual activity. |
| 5.10 | **Smart Search in Admin** | P2 | Natural language search across all admin models. "Show me users who signed up last week and haven't verified email." |
| 5.11 | **Content Moderation Hooks** | P2 | Pluggable moderation pipeline for user-generated content. Text/image moderation via AI APIs. Flagged content review queue in admin. |

### AI Feature Generator

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 5.12 | **Feature Generator: AI Chat** | P1 | `generate_feature chat-ai --provider openai --streaming` |
| 5.13 | **Feature Generator: RAG Knowledge Base** | P2 | `generate_feature knowledge-base --vector-store pgvector` |

---

## v2.2.0 — Multi-Protocol & Advanced Integration

**Theme**: The boilerplate goes beyond REST. gRPC for service-to-service, GraphQL subscriptions for real-time, OAuth2/SAML for enterprise SSO.

### gRPC

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 6.1 | **gRPC Service Generation** | P0 | Generate gRPC service definitions from Django models and services. Proto file generation + server stubs. |
| 6.2 | **gRPC Gateway** | P1 | gRPC alongside REST on the same port via grpc-gateway pattern. Shared auth (JWT → gRPC metadata). |
| 6.3 | **gRPC Client SDK** | P1 | Generated gRPC clients for Python, Go, TypeScript. |

### GraphQL Evolution

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 6.4 | **GraphQL Subscriptions via Centrifugo** | P0 | Bridge Strawberry subscriptions through Centrifugo for real-time GraphQL. Subscription auth via existing Centrifugo JWT flow. |
| 6.5 | **GraphQL Admin Explorer** | P1 | GraphiQL embedded in Unfold admin. Pre-authenticated with session. |
| 6.6 | **GraphQL Federation Readiness** | P2 | Schema design compatible with Apollo Federation / GraphQL Mesh for future service decomposition. |

### Advanced Authentication

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 6.7 | **OAuth2 Provider (RFC 6749)** | P0 | `core/oauth2/` — authorization code, client credentials, refresh token grants. `OAuth2Application` model. Admin UI for managing OAuth2 clients. |
| 6.8 | **SAML 2.0 SSO** | P0 | SAML Service Provider implementation. Integration with Okta, Azure AD, OneLogin. Just-in-time user provisioning. |
| 6.9 | **OpenID Connect (OIDC)** | P1 | OIDC layer on top of OAuth2. Standard claims, ID tokens, discovery endpoint. |
| 6.10 | **Social Login Providers** | P1 | Google, GitHub, Apple, Microsoft. OAuth2-based. Account linking with existing email. |

### Developer Tooling

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 6.11 | **API Mock Server** | P0 | Generate a mock server from OpenAPI spec. Returns realistic fake data. Configurable response delays, error injection. Frontend teams can develop against the mock before the real API exists. |
| 6.12 | **WebSocket Message Persistence** | P1 | Store Centrifugo messages for offline delivery. `MessageRecord` model with TTL. Replay on reconnect. |
| 6.13 | **Webhook Signature Verification SDK v2** | P1 | Production-grade verification libraries with clock-skew tolerance, signature expiration, replay protection. |

### Feature Generator Expansions

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 6.14 | **Feature Generator: OAuth2 Provider** | P2 | `generate_feature oauth2-provider` |
| 6.15 | **Feature Generator: gRPC Service** | P2 | `generate_feature grpc-service --model MyModel` |

---

## v2.3.0 — Infrastructure & Operations Maturity

**Theme**: Production operations at scale. i18n for global reach, distributed locking for correctness, IaC for repeatable infra, and operational tooling.

### Internationalization

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 7.1 | **i18n Framework** | P0 | Django translation strings across all boilerplate code. `Accept-Language` header parsing. Translated API error messages. Locale middleware. |
| 7.2 | **Translated Email Templates** | P1 | Multi-language email templates. Locale-aware template selection. |
| 7.3 | **Admin i18n** | P1 | Translated admin interface. Language switcher in Unfold. |

### Distributed Systems Primitives

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 7.4 | **Distributed Locking** | P0 | Valkey-based distributed locks. `@distributed_lock("resource-key")` decorator. Lock timeout, auto-renewal, fencing tokens for correctness. |
| 7.5 | **Idempotency Keys** | P0 | `IdempotencyKey` model + middleware. Clients send `Idempotency-Key` header. Same key → cached response, no duplicate side effects. Critical for payment/ETL operations. |
| 7.6 | **Circuit Breaker Pattern** | P1 | Circuit breaker for external service calls (Stripe, email, webhooks). Fail-fast when downstream is degraded. Half-open state for recovery. |

### Infrastructure as Code

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 7.7 | **Terraform Modules** | P0 | Reference Terraform for AWS ECS, GCP Cloud Run, Azure Container Apps. RDS/Cloud SQL, ElastiCache/Memorystore, S3/GCS. |
| 7.8 | **Kubernetes Operator** | P1 | Custom K8s operator for auto-scaling based on Celery queue depth + request latency. HPA configuration. |
| 7.9 | **Pulumi Reference Stack** | P2 | Alternative IaC in Python. Same resources as Terraform modules. |

### Operational Tooling

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 7.10 | **Data Catalog / Schema Registry** | P0 | Auto-generated data dictionary from Django models. Field descriptions, types, constraints, relationships. HTML + JSON export. Linked from admin. |
| 7.11 | **Scheduled Reports** | P1 | Auto-generate and email PDF/CSV reports on a schedule. Template-based report definitions. Admin UI to configure. |
| 7.12 | **Feature Flag A/B Test Dashboard** | P1 | Statistical significance calculator, conversion metrics per variant, sample size recommendations. |
| 7.13 | **Cron Expression Builder** | P2 | Visual cron expression builder widget in admin for Celery Beat schedules. Human-readable descriptions. |

### Security Hardening

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 7.14 | **Security.txt & Vulnerability Disclosure** | P2 | Standard `security.txt` endpoint. Vulnerability reporting workflow. |
| 7.15 | **Secrets Rotation** | P1 | Automated rotation for JWT signing keys, Centrifugo secrets, API key secrets. Grace period for old keys during rotation. |
| 7.16 | **CSP & Security Header Audit** | P2 | Comprehensive CSP policy review. Referrer-Policy, Permissions-Policy, X-Content-Type-Options hardening. |

---

## v3.0.0 — Multi-Service Architecture

**Theme**: The boilerplate embraces distributed systems. Not a monolith → microservices migration kit, but rather the *patterns and primitives* that make service decomposition safe: event sourcing, CQRS, sagas, contract testing, and service mesh configuration.

### Service Decomposition Patterns

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 8.1 | **Bounded Context Reference Architecture** | P0 | Documented patterns for splitting the monolith into bounded contexts: auth-service, billing-service, notification-service, etc. Shared kernel, anti-corruption layers. Not generated code — reference architecture + decision framework. |
| 8.2 | **Service Template Generator** | P0 | `make startapp --service my-service` generates a standalone service with its own Django project, shared auth via JWT, and OpenAPI spec. Ready to deploy independently. |
| 8.3 | **Shared Schema Package** | P0 | Extract shared Pydantic schemas, event types, and proto definitions into a versioned Python package. Services depend on the shared package, not each other's code. |

### Event-Driven Architecture

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 8.4 | **Event Sourcing Foundation** | P0 | `core/eventsourcing/` — `EventStore` model (append-only event log), `Aggregate` base class (rebuild state from events), `Projection` base class (materialized views). |
| 8.5 | **CQRS Pattern** | P0 | Separate read models from write models. Command → Event → Projection pipeline. Read-optimized query endpoints backed by materialized views. |
| 8.6 | **Saga Orchestration** | P1 | Saga pattern for distributed transactions. `Saga` base class with compensation steps. Saga execution log for recovery. |
| 8.7 | **Dead Letter Queue for Events** | P1 | DLQ for failed event handlers. Admin UI for inspecting and replaying failed events. Poison message detection. |

### Service Mesh & Communication

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 8.8 | **Service Mesh Configs** | P1 | Reference configs for Linkerd and Istio. mTLS, traffic splitting, retry policies, circuit breaking at the mesh layer. |
| 8.9 | **gRPC Service-to-Service** | P1 | gRPC for internal service communication. Protobuf service definitions, client load balancing, health checking. |
| 8.10 | **API Gateway Pattern** | P1 | Nginx/Kong/Traefik configs for API gateway routing. Rate limiting at the gateway. Auth token validation at the edge. |

### Cross-Service Testing

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 8.11 | **Contract Testing (Pact)** | P0 | Pact contract tests between services. Provider verification in CI. Prevents integration breakage across independently deployed services. |
| 8.12 | **Distributed Tracing Across Services** | P1 | OpenTelemetry context propagation across service boundaries. Trace visualization for cross-service requests. |
| 8.13 | **Chaos Engineering Primitives** | P2 | Optional latency injection, error injection middleware for resilience testing. Controlled via feature flags. |

### Feature Generator: Service

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 8.14 | **Feature Generator: New Service** | P0 | `generate_feature service --name payment-service --with-grpc --with-events` |

---

## Parking Lot — Ideas Beyond v3.0

| # | Idea | Notes |
|---|------|-------|
| P.1 | **Built-in Feature Tiers** | Free/Pro/Enterprise feature gating wired to subscription plans. Dependent on billing maturity. |
| P.2 | **Multi-Region Active-Active** | Cross-region replication patterns, latency-based routing, conflict-free replicated data types (CRDTs). |
| P.3 | **WASM Plugin System** | WebAssembly plugin sandbox for user-defined ETL transforms, webhook handlers, and custom business logic. |
| P.4 | **Edge Computing Support** | Deploy API to Cloudflare Workers / Fly.io regions. SQLite + Litestream at the edge. |
| P.5 | **Real-Time Collaborative Features** | Operational transform (OT) or CRDT-based collaborative editing primitives. Shared via Centrifugo. |
| P.6 | **Blockchain/Web3 Integration** | Wallet auth (SIWE), smart contract event listeners, token-gated API access. |
| P.7 | **Compliance Frameworks** | SOC 2, HIPAA, PCI-DSS compliance checklists and reference configurations. |
| P.8 | **Federated GraphQL** | Full Apollo Federation support. Composed supergraph from independent service subgraphs. |

---

## Dependency Map

```
v1.9.0 (standalone — no dependencies)
  └─► v1.10.0 (observability dashboard uses health endpoints from 1.9)
       └─► v1.11.0 (event bus feeds into observability from 1.10)
            └─► v2.0.0 (ETL uses Celery monitoring from 1.9+1.10; SDKs consume API patterns from 1.11)
                 ├─► v2.1.0 (AI features use event bus from 1.11; observability from 1.10)
                 ├─► v2.2.0 (gRPC/GraphQL extend API patterns from 1.11; OAuth2 uses auth foundation from 2.0)
                 └─► v2.3.0 (distributed locking uses Valkey from 2.0; IaC deploys infra from 2.0)
                      └─► v3.0.0 (event sourcing builds on event bus from 1.11; service mesh deploys infra from 2.3)
```

Versions through 2.x are independently releasable — each adds value without requiring the next.
v3.0.0 is a more significant architectural evolution and benefits from the full 2.x foundation.

---

## Legend

- **P0**: Must-have for the version — version is incomplete without it
- **P1**: High value, ship in the version if timeline allows; otherwise defer to next
- **P2**: Nice-to-have, ship opportunistically or defer
