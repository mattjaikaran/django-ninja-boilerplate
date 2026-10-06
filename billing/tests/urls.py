"""URLconf for billing tests: the project URLs plus the billing controllers.

Billing is an optional app, so ``api/urls.py`` does not register its
controllers. The tests mount them on a separate API under ``/api/`` with the
project's exception handlers, after the project's own URL patterns.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import path
from ninja_extra import NinjaExtraAPI

from api.exceptions import (
    BaseAPIException,
    handle_api_exception,
    handle_django_validation_error,
)
from api.urls import _freeze_operation_contract
from api.urls import urlpatterns as project_urlpatterns
from billing.controllers import BillingController, StripeWebhookController

billing_api = NinjaExtraAPI(
    urls_namespace="billing_test_api", openapi_url=None, docs_url=None
)
billing_api.add_exception_handler(BaseAPIException, handle_api_exception)  # type: ignore[arg-type]
billing_api.add_exception_handler(DjangoValidationError, handle_django_validation_error)  # type: ignore[arg-type]
billing_api.register_controllers(BillingController, StripeWebhookController)
# Same wire contract as the main API: camelCase aliases in responses.
_freeze_operation_contract(billing_api)

urlpatterns = [path("api/", billing_api.urls), *project_urlpatterns]
