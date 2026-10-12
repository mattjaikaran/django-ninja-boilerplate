"""Payments generator templates."""

from core.management.commands.generators.codegen import (
    from_import,
    import_block,
)

# AGENTS.md section 08: JWTAuth on the controller, a thin handler per route
# that calls PaymentService (which owns the ORM and the Stripe calls), and
# static paths before every dynamic handler.
PAYMENTS_CONTROLLER_TEMPLATE = '''"""Payment controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/payments", tags=["Payments"], auth=JWTAuth())
class PaymentController:
    """Payment endpoints for the authenticated user.

    Put static paths before the first /{{payment_id}} handler.
    """

    def __init__(self):
        self.service = PaymentService()

    @http_get("/", response={{200: list[PaymentSchema]}})
    @log_api_call()
    def list_payments(self, request):
        """List the user's payments."""
        return 200, self.service.list_payments(request.user)

    @http_get("/methods", response={{200: list[PaymentMethodSchema]}})
    @log_api_call()
    def list_payment_methods(self, request):
        """List the user's payment methods."""
        return 200, self.service.list_payment_methods(request.user)

    @http_post("/methods", response={{201: PaymentMethodSchema}})
    @log_api_call(include_payload=True)
    def create_payment_method(self, request, payload: CreatePaymentMethodSchema):
        """Attach a Stripe payment method to the user."""
        return 201, self.service.create_payment_method(request.user, payload)

    @http_post("/intents", response={{201: PaymentIntentSchema, 404: dict}})
    @log_api_call(include_payload=True)
    def create_payment_intent(self, request, payload: CreatePaymentIntentSchema):
        """Create a Stripe payment intent for the user."""
        return 201, self.service.create_payment_intent(request.user, payload)

    @http_post("/process", response={{200: PaymentSchema, 404: dict, 409: dict}})
    @log_api_call(include_payload=True)
    def process_payment(self, request, payload: ProcessPaymentSchema):
        """Confirm one of the user's payment intents and record the payment."""
        return 200, self.service.process_payment(request.user, payload)

    @http_delete("/methods/{{method_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_payment_method(self, request, method_id: UUID):
        """Detach and delete one of the user's payment methods."""
        self.service.delete_payment_method(method_id, request.user)
        return 204, None

    @http_get("/{{payment_id}}", response={{200: PaymentSchema, 404: dict}})
    @log_api_call()
    def get_payment(self, request, payment_id: UUID):
        """Get one of the user's payments."""
        return 200, self.service.get_payment(payment_id, request.user)
'''


def render_payments_controller(app_name: str) -> str:
    """Render PAYMENTS_CONTROLLER_TEMPLATE with its first-party imports in isort order."""
    first_party_imports = import_block(
        "from api.decorators import log_api_call",
        from_import(
            f"{app_name}.schemas",
            "CreatePaymentIntentSchema",
            "CreatePaymentMethodSchema",
            "PaymentIntentSchema",
            "PaymentMethodSchema",
            "PaymentSchema",
            "ProcessPaymentSchema",
        ),
        from_import(f"{app_name}.services", "PaymentService"),
    )
    return PAYMENTS_CONTROLLER_TEMPLATE.format(first_party_imports=first_party_imports)
