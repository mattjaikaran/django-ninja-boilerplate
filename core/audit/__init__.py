"""Audit Logging System.

This module provides comprehensive audit logging for compliance tracking:
- Model change tracking via Django signals
- API request/response logging middleware
- Explicit audit actions via decorators
- Admin interface for viewing audit logs
- API endpoints for querying audit logs
"""

from core.audit.decorators import audit_action
from core.audit.signals import setup_audit_signals

__all__ = ["audit_action", "setup_audit_signals"]
