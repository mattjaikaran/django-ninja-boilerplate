"""Base service classes for business logic layer.

This module provides base service classes that can be extended
to implement business logic for different models.
"""

from __future__ import annotations

import builtins
import logging
from typing import Any, Generic, TypeVar
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import QuerySet

from api.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# Type variable for model types
ModelT = TypeVar("ModelT", bound=models.Model)
CreateSchemaT = TypeVar("CreateSchemaT")
UpdateSchemaT = TypeVar("UpdateSchemaT")


class BaseService(Generic[ModelT]):
    """Base service class with common functionality.

    Provides a foundation for implementing business logic services
    with logging, error handling, and common utility methods.

    Attributes:
        model: The Django model class this service operates on
        logger: Logger instance for the service
    """

    model: type[ModelT]

    def __init__(self):
        """Initialize the service."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_queryset(self) -> QuerySet[ModelT]:
        """Get the base queryset for the model.

        Override this method to add default filters, select_related, etc.

        Returns:
            QuerySet of model instances
        """
        return self.model.objects.all()

    def get_active_queryset(self) -> QuerySet[ModelT]:
        """Get queryset of active records only.

        Returns:
            QuerySet of active model instances
        """
        qs = self.get_queryset()
        if hasattr(self.model, "is_active"):
            return qs.filter(is_active=True)
        return qs

    def get_by_id(self, id: str | UUID) -> ModelT | None:
        """Get a single instance by ID.

        Args:
            id: The primary key of the instance

        Returns:
            Model instance or None if not found
        """
        try:
            return self.get_queryset().get(pk=id)
        except ObjectDoesNotExist:
            return None

    def get_by_id_or_raise(self, id: str | UUID) -> ModelT:
        """Get a single instance by ID or raise NotFoundError.

        Args:
            id: The primary key of the instance

        Returns:
            Model instance

        Raises:
            NotFoundError: If instance not found
        """
        instance = self.get_by_id(id)
        if instance is None:
            raise NotFoundError(
                message=f"{self.model.__name__} with id {id} not found",
                code="not_found",
            )
        return instance

    def exists(self, id: str | UUID) -> bool:
        """Check if an instance exists by ID.

        Args:
            id: The primary key to check

        Returns:
            True if exists, False otherwise
        """
        return self.get_queryset().filter(pk=id).exists()

    def count(self, **filters) -> int:
        """Count instances matching filters.

        Args:
            **filters: Django ORM filter kwargs

        Returns:
            Count of matching instances
        """
        return self.get_queryset().filter(**filters).count()


class CRUDService(BaseService[ModelT]):
    """CRUD service class with create, read, update, delete operations.

    Extends BaseService with full CRUD functionality including
    soft delete support and audit tracking.

    Example:
        ```python
        class TodoService(CRUDService[Todo]):
            model = Todo

            def get_queryset(self):
                return super().get_queryset().select_related("user")


        todo_service = TodoService()
        todo = todo_service.create({"title": "New Todo"})
        ```
    """

    def create(self, data: dict[str, Any], user=None) -> ModelT:
        """Create a new instance.

        Args:
            data: Dictionary of field values
            user: Optional user performing the action (for audit)

        Returns:
            Created model instance

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Add audit fields if model supports them
            if user and hasattr(self.model, "created_by"):
                data["created_by"] = user

            with transaction.atomic():
                instance = self.model(**data)
                instance.full_clean()
                instance.save()

            self.logger.info(
                "Created %s with id %s",
                self.model.__name__,
                instance.pk,
            )
            return instance

        except Exception as e:
            self.logger.exception("Failed to create %s: %s", self.model.__name__, e)
            raise ValidationError(message=str(e)) from e

    def update(
        self,
        id: str | UUID,
        data: dict[str, Any],
        user=None,
    ) -> ModelT:
        """Update an existing instance.

        Args:
            id: The primary key of the instance to update
            data: Dictionary of fields to update
            user: Optional user performing the action (for audit)

        Returns:
            Updated model instance

        Raises:
            NotFoundError: If instance not found
            ValidationError: If validation fails
        """
        instance = self.get_by_id_or_raise(id)

        try:
            with transaction.atomic():
                for field, value in data.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)

                # Update audit fields
                if user and hasattr(instance, "updated_by"):
                    instance.updated_by = user

                instance.full_clean()
                instance.save()

            self.logger.info(
                "Updated %s with id %s",
                self.model.__name__,
                id,
            )
            return instance

        except Exception as e:
            self.logger.exception("Failed to update %s: %s", self.model.__name__, e)
            raise ValidationError(message=str(e)) from e

    def partial_update(
        self,
        id: str | UUID,
        data: dict[str, Any],
        user=None,
    ) -> ModelT:
        """Partially update an existing instance (only provided fields).

        Args:
            id: The primary key of the instance to update
            data: Dictionary of fields to update (only non-None values)
            user: Optional user performing the action

        Returns:
            Updated model instance
        """
        # Filter out None values for partial update
        update_data = {k: v for k, v in data.items() if v is not None}
        return self.update(id, update_data, user)

    def delete(self, id: str | UUID, user=None, hard_delete: bool = False) -> bool:
        """Delete an instance (soft delete by default).

        Args:
            id: The primary key of the instance to delete
            user: Optional user performing the action
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If instance not found
        """
        instance = self.get_by_id_or_raise(id)

        if hard_delete or not hasattr(instance, "is_active"):
            instance.delete()
            self.logger.info(
                "Hard deleted %s with id %s",
                self.model.__name__,
                id,
            )
        else:
            instance.soft_delete(user=user)  # type: ignore[attr-defined]
            self.logger.info(
                "Soft deleted %s with id %s",
                self.model.__name__,
                id,
            )

        return True

    def restore(self, id: str | UUID, user=None) -> ModelT:
        """Restore a soft-deleted instance.

        Args:
            id: The primary key of the instance to restore
            user: Optional user performing the action

        Returns:
            Restored model instance

        Raises:
            NotFoundError: If instance not found
        """
        # Use all_objects if available to find soft-deleted records
        queryset = getattr(self.model, "all_objects", self.model.objects)

        try:
            instance = queryset.get(pk=id)
        except ObjectDoesNotExist as e:
            raise NotFoundError(
                message=f"{self.model.__name__} with id {id} not found",
            ) from e

        if hasattr(instance, "restore"):
            instance.restore(user=user)
            self.logger.info(
                "Restored %s with id %s",
                self.model.__name__,
                id,
            )

        return instance

    def list(
        self,
        filters: dict[str, Any] | None = None,
        ordering: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> QuerySet[ModelT]:
        """List instances with optional filtering and ordering.

        Args:
            filters: Dictionary of filter conditions
            ordering: Field to order by (prefix with - for descending)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            QuerySet of matching instances
        """
        queryset = self.get_queryset()

        if filters:
            queryset = queryset.filter(**filters)

        if ordering:
            queryset = queryset.order_by(ordering)

        if offset:
            queryset = queryset[offset:]

        if limit:
            queryset = queryset[:limit]

        return queryset

    def bulk_create(
        self,
        data_list: builtins.list[dict[str, Any]],
        user=None,
        batch_size: int = 100,
    ) -> builtins.list[ModelT]:
        """Bulk create multiple instances.

        Args:
            data_list: List of dictionaries with field values
            user: Optional user performing the action
            batch_size: Number of objects to create per batch

        Returns:
            List of created instances
        """
        instances = []
        for data in data_list:
            if user and hasattr(self.model, "created_by"):
                data["created_by"] = user
            instances.append(self.model(**data))

        created = self.model.objects.bulk_create(instances, batch_size=batch_size)
        self.logger.info(
            "Bulk created %d %s instances",
            len(created),
            self.model.__name__,
        )
        return created

    def bulk_update(
        self,
        instances: builtins.list[ModelT],
        fields: builtins.list[str],
        user=None,
        batch_size: int = 100,
    ) -> int:
        """Bulk update multiple instances.

        Args:
            instances: List of model instances to update
            fields: List of field names to update
            user: Optional user performing the action
            batch_size: Number of objects to update per batch

        Returns:
            Number of updated instances
        """
        if user and "updated_by" not in fields and hasattr(self.model, "updated_by"):
            for instance in instances:
                instance.updated_by = user
            fields.append("updated_by")

        count = self.model.objects.bulk_update(
            instances,
            fields,
            batch_size=batch_size,
        )
        self.logger.info(
            "Bulk updated %d %s instances",
            count,
            self.model.__name__,
        )
        return count

    def bulk_delete(
        self,
        ids: builtins.list[str | UUID],
        user=None,
        hard_delete: bool = False,
    ) -> int:
        """Bulk delete multiple instances.

        Args:
            ids: List of primary keys to delete
            user: Optional user performing the action
            hard_delete: If True, permanently delete

        Returns:
            Number of deleted instances
        """
        queryset = self.get_queryset().filter(pk__in=ids)

        if hard_delete or not hasattr(self.model, "is_active"):
            count, _ = queryset.delete()
        else:
            update_data = {"is_active": False}
            if hasattr(self.model, "updated_by") and user:
                update_data["updated_by"] = user
            count = queryset.update(**update_data)

        self.logger.info(
            "Bulk deleted %d %s instances",
            count,
            self.model.__name__,
        )
        return count
