from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from api.healthcheck import HealthCheckController
from api.parsers import ORJSONParser
from api.renderers import ORJSONRenderer
from atlas.views import atlas_admin_view, atlas_data_view, atlas_regenerate_view

# Optional app imports — uncomment to enable:
# from billing.controllers import BillingController, StripeWebhookController
from core.controllers import (
    APIKeyController,
    AuditLogController,
    AuthController,
    CentrifugoTokenController,
    DeadLetterQueueController,
    OTPController,
    TaskController,
    TaskSchedulerController,
    UserController,
)
from core.observability.admin_views import health_admin_view, metrics_admin_view
from core.observability.controllers import EnhancedHealthController, MetricsController
from core.sse.views import sse_endpoint

# from files.controllers import FileController
# from notifications.controllers import NotificationController
# from organizations.controllers import OrganizationController
from todos.controllers import (
    TodoController,
    TodoControllerBasic,
    TodoControllerDeclarative,
    TodoControllerPartial,
)

# from webhooks.controllers import WebhookController

# admin site settings
admin.site.site_header = "Django Ninja Boilerplate Admin"
admin.site.site_title = "Django Ninja Boilerplate Panel"
admin.site.index_title = "Welcome to Django Ninja Boilerplate Panel"
admin.site.site_url = "/api/docs"

# Instantiate the server
# normally for django-ninja it looks like: api = NinjaAPI()
# ninja extra normally looks like: api = NinjaExtraAPI()
# Below we are adding in Swagger/OpenAPI params
# seen at http://localhost:8000/api/docs

api = NinjaExtraAPI(
    # csrf=True,  # this line is to enable CSRF protection
    openapi_extra={
        "info": {
            "termsOfService": "https://example.com/terms/",
        }
    },
    version="0.1",
    title="Django Ninja Boilerplate API",
    description="API documentation for the Django Ninja Boilerplate API",
    urls_namespace="boilerplate_api",
    renderer=ORJSONRenderer(),
    parser=ORJSONParser(),
    # docs=Redoc(),  # this line is to use ReDoc instead of Swagger
)


# Register controllers
# The order of the controllers matches the order in the API Docs (Swager or ReDoc)
# http://localhost:8000/api/docs
api.register_controllers(
    NinjaJWTDefaultController,  # JWT Auth. If you want to use JWT, you must include this https://github.com/eadwinCode/django-ninja-jwt
    # System controllers
    HealthCheckController,  # Health Check Controller
    EnhancedHealthController,  # Enhanced Health Check Controller (detailed status)
    MetricsController,  # Prometheus Metrics Controller
    # core app
    UserController,  # User Controller
    AuthController,  # Auth Controller (email/password + magic links)
    OTPController,  # OTP Controller (6-digit codes for mobile/iOS apps)
    APIKeyController,  # API Key management (create, list, revoke, rotate)
    CentrifugoTokenController,  # Centrifugo real-time token endpoints
    AuditLogController,  # Audit Log Controller (admin only)
    # Task management controllers
    TaskController,  # Task status and progress tracking
    TaskSchedulerController,  # Periodic task management
    DeadLetterQueueController,  # Failed task handling
    # Optional app controllers — uncomment to enable:
    # FileController,  # files app — S3 presigned upload pattern
    # WebhookController,  # webhooks app — outbound webhooks
    # OrganizationController,  # organizations app — multi-tenancy
    # NotificationController,  # notifications app — in-app + email
    # BillingController,  # billing app — Stripe plans + subscriptions
    # StripeWebhookController,  # billing app — Stripe webhooks
    # todos app — four controllers demonstrating progressively abstracted patterns
    TodoController,  # Pattern 4: full decorators + service layer (recommended)
    TodoControllerPartial,  # Pattern 3: selective decorators, inline DB ops
    TodoControllerBasic,  # Pattern 2: no decorators, get_object_or_404 only
    TodoControllerDeclarative,  # Pattern 1: explicit try/except, maximum verbosity
    # Add more controllers here
)

# add the urls to the urlpatterns
urlpatterns = [
    # Codebase atlas admin pages (must precede the admin catch-all)
    path("admin/atlas/data.json", atlas_data_view, name="atlas_data"),
    path("admin/atlas/regenerate/", atlas_regenerate_view, name="atlas_regenerate"),
    path("admin/atlas/", atlas_admin_view, name="atlas_admin"),
    # Observability admin pages (must precede the admin catch-all)
    path("admin/observability/health/", health_admin_view, name="health_admin"),
    path("admin/observability/metrics/", metrics_admin_view, name="metrics_admin"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    # SSE streaming endpoint (outside Ninja so it can use StreamingHttpResponse)
    path("api/events/stream/", sse_endpoint),
]

# Conditionally mount versioned API instances
if getattr(settings, "API_VERSIONING_ENABLED", False):
    from api.versioning import api_v1, api_v2

    api_v1.register_controllers(
        NinjaJWTDefaultController,
        AuthController,
        UserController,
        OTPController,
        # Optional — uncomment to enable:
        # FileController,
        # WebhookController,
        # OrganizationController,
        # NotificationController,
        # BillingController,
        # StripeWebhookController,
    )

    urlpatterns += [
        path("api/v1/", api_v1.urls),
        path("api/v2/", api_v2.urls),
    ]

# Add debug toolbar URLs if available and in debug mode
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    try:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns += debug_toolbar_urls()
    except ImportError:
        pass

# this is for the static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
