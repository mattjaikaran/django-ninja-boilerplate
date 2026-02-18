"""Controller mixins for common patterns.

Provides reusable mixin classes for Django Ninja Extra controllers.
"""

import logging
from uuid import UUID

from django.shortcuts import get_object_or_404

from api.decorators import handle_exceptions, log_api_call

logger = logging.getLogger(__name__)


class SoftDeleteMixin:
    """Mixin that adds soft delete and restore endpoints to a controller.

    Requires the controller to define a `model` class attribute pointing
    to a model that inherits from SoftDeleteBaseModel.

    Usage:
        @api_controller("/items", tags=["Items"])
        class ItemController(SoftDeleteMixin):
            model = Item

            # Your other endpoints...
            # soft_delete and restore are automatically available
    """

    model = None

    @staticmethod
    def _get_model(cls):
        """Get the model class from the mixin host."""
        if cls.model is None:
            msg = (
                f"{cls.__class__.__name__} must define a 'model' attribute "
                "to use SoftDeleteMixin"
            )
            raise NotImplementedError(msg)
        return cls.model

    @handle_exceptions()
    @log_api_call()
    def soft_delete(self, request, pk: UUID):
        """Soft delete a record by setting is_active=False."""
        model = self._get_model(self)
        obj = get_object_or_404(model, pk=pk)

        user = request.user if request.user.is_authenticated else None
        obj.soft_delete(user=user)

        logger.info("Soft deleted %s %s", model.__name__, pk)
        return 200, {"message": f"{model.__name__} soft deleted", "id": str(pk)}

    @handle_exceptions()
    @log_api_call()
    def restore(self, request, pk: UUID):
        """Restore a soft-deleted record."""
        model = self._get_model(self)
        # Use all_objects or the base manager to find deleted records
        manager = getattr(model, "all_objects", model._default_manager)
        obj = get_object_or_404(manager, pk=pk)

        user = request.user if request.user.is_authenticated else None
        obj.restore(user=user)

        logger.info("Restored %s %s", model.__name__, pk)
        return 200, {"message": f"{model.__name__} restored", "id": str(pk)}
