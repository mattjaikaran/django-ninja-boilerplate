"""Core services package.

This module exports all service classes for the core app.
"""

from core.services.base_service import BaseService, CRUDService

__all__ = [
    "BaseService",
    "CRUDService",
]
