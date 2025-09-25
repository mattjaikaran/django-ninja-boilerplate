"""Controller templates for code generation."""

MODERN_CONTROLLER_TEMPLATE = '''"""{{app_name}} controllers."""

import logging
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from api.search_filters import {{search_filter_class}}, get_{{app_name}}_search_engine
from {{app_name}}.models import {{model_name}}
from {{app_name}}.schemas import {{model_name}}Schema, Create{{model_name}}Schema, Update{{model_name}}Schema

logger = logging.getLogger(__name__)


@api_controller("/{{url_prefix}}", tags=["{{model_name_plural}}"])
class {{model_name}}Controller:
    @list_endpoint(
        cache_timeout=300,
        select_related={{select_related}},
        search_fields={{search_fields}},
        filter_fields={{filter_fields}},
        ordering_fields={{ordering_fields}},
    )
    @http_get("/all", response={{200: list[{{model_name}}Schema]}})
    def list_all_{{url_prefix}}(self, request, filters: {{search_filter_class}} = None):  # noqa: ARG002
        """List all {{model_name_lower}} with search, filtering, and pagination."""
        queryset = {{model_name}}.objects.all()

        if filters:
            search_engine = get_{{app_name}}_search_engine()
            queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @list_endpoint(
        cache_timeout=300,
        select_related={{select_related}},
        search_fields={{search_fields}},
        filter_fields={{filter_fields}},
        ordering_fields={{ordering_fields}},
    )
    @http_get("/", response={{200: list[{{model_name}}Schema]}})
    def list_user_{{url_prefix}}(self, request, filters: {{search_filter_class}} = None):
        """List {{model_name_lower}} for authenticated user with search, filtering, and pagination."""
        user = request.user
        queryset = {{model_name}}.objects.filter(user=user)

        if filters:
            search_engine = get_{{app_name}}_search_engine()
            queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @create_endpoint()
    @http_post("/", response={{201: {{model_name}}Schema}})
    def create_{{model_name_lower}}(self, request, payload: Create{{model_name}}Schema):
        """Create a new {{model_name_lower}} for the authenticated user."""
        user = request.user
        {{model_name_lower}} = {{model_name}}.objects.create(user=user, **payload.dict())
        return 201, {{model_name_lower}}

    @detail_endpoint(select_related={{select_related}})
    @http_get("/{{{{str:{{model_name_lower}}_id}}}}", response={{200: {{model_name}}Schema, 404: dict}})
    def get_{{model_name_lower}}(self, request, {{model_name_lower}}_id: str):
        """Get a specific {{model_name_lower}} by ID for the authenticated user."""
        user = request.user
        {{model_name_lower}} = get_object_or_404({{model_name}}, id={{model_name_lower}}_id, user=user)
        return 200, {{model_name_lower}}

    @update_endpoint(select_related={{select_related}})
    @http_put("/{{{{str:{{model_name_lower}}_id}}}}", response={{200: {{model_name}}Schema, 404: dict}})
    def update_{{model_name_lower}}(self, request, {{model_name_lower}}_id: str, payload: Update{{model_name}}Schema):
        """Update a specific {{model_name_lower}} by ID for the authenticated user."""
        user = request.user
        {{model_name_lower}} = get_object_or_404({{model_name}}, id={{model_name_lower}}_id, user=user)

        # Apply updates
        for key, value in payload.dict(exclude_unset=True).items():
            setattr({{model_name_lower}}, key, value)
        {{model_name_lower}}.save()

        return 200, {{model_name_lower}}

    @delete_endpoint()
    @http_delete("/{{{{str:{{model_name_lower}}_id}}}}", response={{204: dict, 404: dict}})
    def delete_{{model_name_lower}}(self, request, {{model_name_lower}}_id: str):
        """Delete a specific {{model_name_lower}} by ID for the authenticated user."""
        user = request.user
        {{model_name_lower}} = get_object_or_404({{model_name}}, id={{model_name_lower}}_id, user=user)
        {{model_name_lower}}.delete()
        return 204, {{"message": "{{model_name}} deleted successfully"}}
'''

PAYMENTS_CONTROLLER_TEMPLATE = '''"""Payment controllers."""

import logging
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from {{app_name}}.models import Payment, PaymentMethod, PaymentIntent
from {{app_name}}.schemas.payment_schema import (
    PaymentSchema,
    PaymentMethodSchema,
    PaymentIntentSchema,
    CreatePaymentMethodSchema,
    CreatePaymentIntentSchema,
    ProcessPaymentSchema,
)
from {{app_name}}.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


@api_controller("/payments", tags=["Payments"])
class PaymentController:
    """Payment management controller."""

    def __init__(self):
        self.stripe_service = StripeService()

    @list_endpoint(cache_timeout=300)
    @http_get("/methods", response={{200: list[PaymentMethodSchema]}})
    def list_payment_methods(self, request):
        """List user's payment methods."""
        methods = PaymentMethod.objects.filter(user=request.user)
        return 200, methods

    @create_endpoint()
    @http_post("/methods", response={{201: PaymentMethodSchema}})
    def create_payment_method(self, request, payload: CreatePaymentMethodSchema):
        """Create a new payment method."""
        payment_method = self.stripe_service.create_payment_method(
            request.user, payload.stripe_payment_method_id
        )
        return 201, payment_method

    @delete_endpoint()
    @http_delete("/methods/{{str:method_id}}", response={{204: dict}})
    def delete_payment_method(self, request, method_id: str):
        """Delete a payment method."""
        method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
        self.stripe_service.delete_payment_method(method)
        return 204, {{"message": "Payment method deleted successfully"}}

    @create_endpoint()
    @http_post("/intents", response={{201: PaymentIntentSchema}})
    def create_payment_intent(self, request, payload: CreatePaymentIntentSchema):
        """Create a payment intent."""
        intent = self.stripe_service.create_payment_intent(
            user=request.user,
            amount=payload.amount,
            currency=payload.currency,
            payment_method_id=payload.payment_method_id,
            description=payload.description,
        )
        return 201, intent

    @create_endpoint()
    @http_post("/process", response={{200: PaymentSchema}})
    def process_payment(self, request, payload: ProcessPaymentSchema):
        """Process a payment."""
        payment = self.stripe_service.process_payment(
            user=request.user,
            payment_intent_id=payload.payment_intent_id,
            payment_method_id=payload.payment_method_id,
        )
        return 200, payment

    @list_endpoint(cache_timeout=300)
    @http_get("/", response={{200: list[PaymentSchema]}})
    def list_payments(self, request):
        """List user's payments."""
        payments = Payment.objects.filter(user=request.user)
        return 200, payments

    @detail_endpoint()
    @http_get("/{{str:payment_id}}", response={{200: PaymentSchema, 404: dict}})
    def get_payment(self, request, payment_id: str):
        """Get a specific payment."""
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        return 200, payment
'''

RBAC_CONTROLLER_TEMPLATE = '''"""RBAC controllers."""

import logging
from uuid import UUID

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    admin_endpoint,
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from {{app_name}}.models import Role, Permission, UserRole
from {{app_name}}.schemas.rbac_schema import (
    RoleSchema,
    PermissionSchema,
    UserRoleSchema,
    AssignRoleSchema,
    CreateRoleSchema,
    UpdateRoleSchema,
    CreatePermissionSchema,
    UserPermissionsSchema,
)
from {{app_name}}.services.rbac_service import RBACService
from {{app_name}}.decorators import require_permission

User = get_user_model()
logger = logging.getLogger(__name__)


@api_controller("/rbac", tags=["RBAC"])
class RBACController:
    """RBAC management controller."""

    @list_endpoint(cache_timeout=300, require_admin=True)
    @require_permission("view_roles")
    @http_get("/roles", response={{200: list[RoleSchema]}})
    def list_roles(self, request):
        """List all roles."""
        roles = Role.objects.prefetch_related("permissions").all()
        return 200, roles

    @create_endpoint(require_admin=True)
    @require_permission("manage_roles")
    @http_post("/roles", response={{201: RoleSchema}})
    def create_role(self, request, payload: CreateRoleSchema):
        """Create a new role."""
        role = Role.objects.create(
            name=payload.name,
            description=payload.description
        )

        if payload.permission_ids:
            permissions = Permission.objects.filter(id__in=payload.permission_ids)
            role.permissions.set(permissions)

        return 201, role

    @update_endpoint(require_admin=True)
    @require_permission("manage_roles")
    @http_put("/roles/{{str:role_id}}", response={{200: RoleSchema, 404: dict}})
    def update_role(self, request, role_id: str, payload: UpdateRoleSchema):
        """Update a role."""
        role = get_object_or_404(Role, id=role_id)

        if payload.name is not None:
            role.name = payload.name
        if payload.description is not None:
            role.description = payload.description

        role.save()

        if payload.permission_ids is not None:
            permissions = Permission.objects.filter(id__in=payload.permission_ids)
            role.permissions.set(permissions)

        return 200, role

    @delete_endpoint(require_admin=True)
    @require_permission("manage_roles")
    @http_delete("/roles/{{str:role_id}}", response={{204: dict, 404: dict}})
    def delete_role(self, request, role_id: str):
        """Delete a role."""
        role = get_object_or_404(Role, id=role_id)
        role.delete()
        return 204, {{"message": "Role deleted successfully"}}

    @list_endpoint(cache_timeout=300, require_admin=True)
    @require_permission("view_permissions")
    @http_get("/permissions", response={{200: list[PermissionSchema]}})
    def list_permissions(self, request):
        """List all permissions."""
        permissions = Permission.objects.all()
        return 200, permissions

    @create_endpoint(require_admin=True)
    @require_permission("manage_roles")
    @http_post("/permissions", response={{201: PermissionSchema}})
    def create_permission(self, request, payload: CreatePermissionSchema):
        """Create a new permission."""
        permission = Permission.objects.create(
            name=payload.name,
            codename=payload.codename,
            description=payload.description
        )
        return 201, permission

    @create_endpoint(require_admin=True)
    @require_permission("manage_roles")
    @http_post("/users/{{str:user_id}}/roles", response={{201: UserRoleSchema}})
    def assign_role_to_user(self, request, user_id: str, payload: AssignRoleSchema):
        """Assign a role to a user."""
        user = get_object_or_404(User, id=user_id)
        role = get_object_or_404(Role, id=payload.role_id)

        # TODO: Handle object-level permissions if content_type and object_id provided

        user_role = RBACService.assign_role_to_user(user, role)
        return 201, user_role

    @delete_endpoint(require_admin=True)
    @require_permission("manage_roles")
    @http_delete("/users/{{str:user_id}}/roles/{{str:role_id}}", response={{204: dict}})
    def remove_role_from_user(self, request, user_id: str, role_id: str):
        """Remove a role from a user."""
        user = get_object_or_404(User, id=user_id)
        role = get_object_or_404(Role, id=role_id)

        success = RBACService.remove_role_from_user(user, role)
        if success:
            return 204, {{"message": "Role removed successfully"}}
        else:
            return 400, {{"error": "Role assignment not found"}}

    @detail_endpoint(require_admin=True)
    @require_permission("view_user_permissions")
    @http_get("/users/{{str:user_id}}/permissions", response={{200: UserPermissionsSchema}})
    def get_user_permissions(self, request, user_id: str):
        """Get user's permissions and roles."""
        user = get_object_or_404(User, id=user_id)
        permissions = RBACService.get_user_permissions(user)
        user_roles = UserRole.objects.filter(user=user).select_related("role")

        return 200, {{
            "user_id": str(user.id),
            "username": user.username,
            "permissions": permissions,
            "roles": user_roles,
        }}
'''
