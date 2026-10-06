import math
import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import path
from ninja.errors import Throttled
from ninja_extra import ControllerBase, NinjaExtraAPI, api_controller
from ninja_extra.permissions import AllowAny
from ninja_extra.throttling import DynamicRateThrottle
from ninja_jwt.controller import TokenObtainPairController, TokenVerificationController

from api.exceptions import (
    BaseAPIException,
    handle_api_exception,
    handle_django_validation_error,
    handle_generic_exception,
)
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
    SessionController,
    TaskController,
    TaskSchedulerController,
    UserController,
)
from core.observability.admin_views import health_admin_view, metrics_admin_view
from core.observability.controllers import MetricsController
from core.security.brute_force import admin_login_with_lockout
from core.sse.views import sse_endpoint

# from notifications.controllers import NotificationController
# from organizations.controllers import OrganizationController
from todos.controllers import (
    TodoController,
    TodoControllerBasic,
    TodoControllerDeclarative,
    TodoControllerPartial,
)

# admin site settings
admin.site.site_header = "Django Ninja Boilerplate Admin"
admin.site.site_title = "Django Ninja Boilerplate Panel"
admin.site.index_title = "Welcome to Django Ninja Boilerplate Panel"
# The header "View site" link points at the docs, or is hidden when API_DOCS=off.
admin.site.site_url = "/api/docs" if settings.API_DOCS != "off" else None

# Instantiate the server
# normally for django-ninja it looks like: api = NinjaAPI()
# ninja extra normally looks like: api = NinjaExtraAPI()
# Below we are adding in Swagger/OpenAPI params
# seen at http://localhost:8000/api/docs

# API_DOCS (settings): "public", "staff" (admin login) or "off" (prod default).
_docs_enabled = settings.API_DOCS != "off"

api = NinjaExtraAPI(
    # CSRF for the API lives in core.security.cookie_auth.ApiCsrfMiddleware.
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
    openapi_url="/openapi.json" if _docs_enabled else None,
    docs_url="/docs" if _docs_enabled else None,
    docs_decorator=staff_member_required if settings.API_DOCS == "staff" else None,
    # docs=Redoc(),  # this line is to use ReDoc instead of Swagger
)


# Ninja's handler stub admits exception classes, but runtime supplies instances.
api.add_exception_handler(BaseAPIException, handle_api_exception)  # type: ignore[arg-type]
api.add_exception_handler(DjangoValidationError, handle_django_validation_error)  # type: ignore[arg-type]
api.add_exception_handler(Exception, handle_generic_exception)  # type: ignore[arg-type]


def handle_throttled(request, exc: Throttled):
    """Return 429 with real retry metadata for throttled requests."""
    retry_after = max(1, math.ceil(exc.wait or 1))
    response = api.create_response(
        request,
        {"detail": str(exc), "retry_after": retry_after},
        status=429,
    )
    response["Retry-After"] = str(retry_after)
    return response


api.add_exception_handler(Throttled, handle_throttled)  # type: ignore[arg-type]


# ninja-jwt's NinjaJWTDefaultController has no throttle, so /api/token/pair
# allowed unlimited password guessing beside the throttled /api/auth/login.
# Same routes and operationIds, with the credential-endpoint throttle.
@api_controller(
    "/token",
    permissions=[AllowAny],
    tags=["token"],
    auth=None,
    throttle=DynamicRateThrottle(scope="anon-auth"),
)
class ThrottledJWTController(
    ControllerBase, TokenVerificationController, TokenObtainPairController
):
    """Obtain, refresh and verify JWT pairs (bearer clients)."""

    auto_import = False


# Register controllers
# The order of the controllers matches the order in the API Docs (Swager or ReDoc)
# http://localhost:8000/api/docs
api.register_controllers(
    ThrottledJWTController,  # JWT pair/refresh/verify for bearer clients (throttled)
    # System controllers
    HealthCheckController,  # Health Check Controller (liveness/readiness/detailed/component)
    MetricsController,  # Prometheus Metrics Controller (staff only)
    # core app
    UserController,  # User Controller
    AuthController,  # Auth Controller (email/password + magic links)
    SessionController,  # Cookie session: CSRF, refresh rotation, logout
    OTPController,  # OTP Controller (6-digit codes for mobile/iOS apps)
    APIKeyController,  # API Key management (create, list, revoke, rotate)
    CentrifugoTokenController,  # Centrifugo real-time token endpoints
    AuditLogController,  # Audit Log Controller (admin only)
    # Task management controllers
    TaskController,  # Task status and progress tracking
    TaskSchedulerController,  # Periodic task management
    DeadLetterQueueController,  # Failed task handling
    # Optional app controllers — uncomment to enable:
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

# Optional apps behind flags in api/settings/common.py. Both default off.
if settings.FILES_ENABLED:
    from files.controllers import FileController

    api.register_controllers(FileController)  # files app: S3 presigned upload
if settings.WEBHOOKS_ENABLED:
    from webhooks.controllers import WebhookController

    api.register_controllers(WebhookController)  # webhooks app: outbound webhooks

# ninja-extra appends a random 8-hex suffix to generated operationIds
# (``use_unique_op_id``). The frontend client is generated from these ids.
_RANDOM_OP_ID_SUFFIX = re.compile(r"_[0-9a-f]{8}$")


def _freeze_operation_contract(ninja_api: NinjaExtraAPI) -> None:
    """Make the exported OpenAPI contract match the wire and stay stable.

    1. Serialise and document every response by alias. CamelCaseSchema
       aliases are the wire contract, and ninja-extra has no API-wide
       ``by_alias`` default (request bodies already use aliases).
    2. Strip ninja-extra's random operationId suffix so
       ``docs/openapi/openapi.json`` is the same on every export.
    """
    seen: dict[str, str] = {}
    for _prefix, router in ninja_api._routers:
        for route, path_view in router.path_operations.items():
            for operation in path_view.operations:
                operation.by_alias = True
                if operation.operation_id:
                    operation_id = _RANDOM_OP_ID_SUFFIX.sub("", operation.operation_id)
                    if operation_id in seen:
                        raise ImproperlyConfigured(
                            f"Duplicate operationId {operation_id!r} on {route} and "
                            f"{seen[operation_id]}; rename one handler."
                        )
                    seen[operation_id] = route
                    operation.operation_id = operation_id


_freeze_operation_contract(api)

# ADMIN_URL (settings, default "admin/") mounts the admin and its extra pages.
_admin = settings.ADMIN_URL

# add the urls to the urlpatterns
urlpatterns = [
    # Codebase atlas admin pages (must precede the admin catch-all)
    path(f"{_admin}atlas/data.json", atlas_data_view, name="atlas_data"),
    path(f"{_admin}atlas/regenerate/", atlas_regenerate_view, name="atlas_regenerate"),
    path(f"{_admin}atlas/", atlas_admin_view, name="atlas_admin"),
    # Observability admin pages (must precede the admin catch-all)
    path(f"{_admin}observability/health/", health_admin_view, name="health_admin"),
    path(f"{_admin}observability/metrics/", metrics_admin_view, name="metrics_admin"),
    # Admin login with the shared per-account and per-IP lockout.
    path(f"{_admin}login/", admin_login_with_lockout, name="admin_login_lockout"),
    path(_admin, admin.site.urls),
    path("api/", api.urls),
    # SSE streaming endpoint (outside Ninja so it can use StreamingHttpResponse)
    path("api/events/stream/", sse_endpoint),
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
