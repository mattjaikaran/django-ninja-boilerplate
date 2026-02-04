"""Feature Flags Module.

This module provides a comprehensive feature flags system for:
- Toggle features per user/tenant/environment
- Gradual rollouts (percentage-based)
- A/B testing support
"""

from .decorators import feature_flag, require_feature
from .service import FeatureFlagService, feature_flag_service

__all__ = [
    "FeatureFlagService",
    "feature_flag_service",
    "feature_flag",
    "require_feature",
]
