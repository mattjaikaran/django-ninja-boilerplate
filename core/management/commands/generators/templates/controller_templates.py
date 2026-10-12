"""Controller templates for code generation."""

from core.management.commands.generators.codegen import (
    ResourceNames,
    from_import,
    import_block,
    method_def,
)

# AGENTS.md section 08: JWTAuth on the controller, a thin handler per route
# that calls the owner-scoped service, no try/except around lookups, and
# static paths before every /{item_id} handler.
CONTROLLER_TEMPLATE = '''"""{model_name} controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/{route}", tags=["{tag}"], auth=JWTAuth())
class {model_name}Controller:
    """CRUD endpoints for the authenticated user's {route}.

    Put static paths before the first /{{item_id}} handler.
    """

    def __init__(self):
        self.service = {model_name}Service()

    @http_get("/", response={{200: list[{model_name}Schema]}})
    @log_api_call()
    def list_{route}(self, request):
        """List the user's {route}."""
        return 200, self.service.list_for_user(request.user)

    @http_post("/", response={{201: {model_name}Schema}})
    @log_api_call(include_payload=True)
{create_def}
        """Create a {model_snake} for the user."""
        return 201, self.service.create(request.user, payload)

    @http_get("/{{item_id}}", response={{200: {model_name}Schema, 404: dict}})
    @log_api_call()
    def get_{model_snake}(self, request, item_id: UUID):
        """Get one of the user's {route}."""
        return 200, self.service.get_for_user(item_id, request.user)

    @http_put("/{{item_id}}", response={{200: {model_name}Schema, 404: dict}})
    @log_api_call(include_payload=True)
{update_def}
        """Update one of the user's {route}."""
        return 200, self.service.update(item_id, request.user, payload)

    @http_delete("/{{item_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_{model_snake}(self, request, item_id: UUID):
        """Delete one of the user's {route}."""
        self.service.delete(item_id, request.user)
        return 204, None
'''


def render_controller(names: ResourceNames) -> str:
    """Render CONTROLLER_TEMPLATE with its first-party imports in isort order."""
    model = names.model_name
    first_party_imports = import_block(
        "from api.decorators import log_api_call",
        from_import(
            f"{names.app_name}.schemas",
            f"{model}Schema",
            f"Create{model}Schema",
            f"Update{model}Schema",
        ),
        from_import(f"{names.app_name}.services", f"{model}Service"),
    )
    return CONTROLLER_TEMPLATE.format(
        first_party_imports=first_party_imports,
        create_def=method_def(
            f"create_{names.model_snake}",
            f"self, request, payload: Create{model}Schema",
        ),
        update_def=method_def(
            f"update_{names.model_snake}",
            f"self, request, item_id: UUID, payload: Update{model}Schema",
        ),
        **names.context(),
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


# Staff-only RBAC management (IsAdminUser on the controller). The one route a
# regular user may call is GET /me/permissions, for their own roles. Rendered
# with str.format, so literal braces are doubled.
RBAC_CONTROLLER_TEMPLATE = '''"""RBAC controller. Staff manage roles; each user reads their own permissions."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/rbac", tags=["RBAC"], auth=JWTAuth(), permissions=[IsAdminUser])
class RBACController:
    """Role and permission management.

    Every route is staff-only (IsAdminUser) except GET /me/permissions, which
    any authenticated user calls for their own roles and permissions. Put
    static paths before the first dynamic handler.
    """

    def __init__(self):
        self.service = RBACService()

    @http_get(
        "/me/permissions",
        response={{200: UserPermissionsSchema}},
        permissions=[IsAuthenticated],
    )
    @log_api_call()
    def get_my_permissions(self, request):
        """Get the authenticated user's roles and permissions."""
        return 200, self.service.permissions_summary(request.user)

    @http_get("/roles", response={{200: list[RoleSchema]}})
    @log_api_call()
    def list_roles(self, request):
        """List every role with its permissions."""
        return 200, self.service.list_roles()

    @http_post("/roles", response={{201: RoleSchema, 400: dict, 409: dict}})
    @log_api_call(include_payload=True)
    def create_role(self, request, payload: CreateRoleSchema):
        """Create a role."""
        return 201, self.service.create_role(payload)

    @http_get("/permissions", response={{200: list[PermissionSchema]}})
    @log_api_call()
    def list_permissions(self, request):
        """List every permission."""
        return 200, self.service.list_permissions()

    @http_post("/permissions", response={{201: PermissionSchema, 409: dict}})
    @log_api_call(include_payload=True)
    def create_permission(self, request, payload: CreatePermissionSchema):
        """Create a permission."""
        return 201, self.service.create_permission(payload)

    @http_put(
        "/roles/{{role_id}}",
        response={{200: RoleSchema, 400: dict, 404: dict, 409: dict}},
    )
    @log_api_call(include_payload=True)
    def update_role(self, request, role_id: UUID, payload: UpdateRoleSchema):
        """Update a role."""
        return 200, self.service.update_role(role_id, payload)

    @http_delete("/roles/{{role_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_role(self, request, role_id: UUID):
        """Delete a role."""
        self.service.delete_role(role_id)
        return 204, None

    @http_get(
        "/users/{{user_id}}/permissions",
        response={{200: UserPermissionsSchema, 404: dict}},
    )
    @log_api_call()
    def get_user_permissions(self, request, user_id: UUID):
        """Get a user's roles and permissions."""
        return 200, self.service.get_user_summary(user_id)

    @http_post("/users/{{user_id}}/roles", response={{201: UserRoleSchema, 404: dict}})
    @log_api_call(include_payload=True)
    def assign_role(self, request, user_id: UUID, payload: AssignRoleSchema):
        """Assign a global role to a user."""
        return 201, self.service.assign_role(user_id, payload.role_id)

    @http_delete("/users/{{user_id}}/roles/{{role_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def remove_role(self, request, user_id: UUID, role_id: UUID):
        """Remove a global role from a user."""
        self.service.remove_role(user_id, role_id)
        return 204, None
'''
