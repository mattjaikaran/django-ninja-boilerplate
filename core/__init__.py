"""Core Application
---------------
This app provides essential functionality for user management,
authentication, and base structures for the entire project.

Includes:
- User management and authentication
- Feature flags system for rollouts and A/B testing
- Audit logging
- OTP (One-Time Password) support

Feature Flags Usage:
    from core.features import feature_flag_service, feature_flag

    # Check if a flag is enabled
    if feature_flag_service.is_enabled("new_feature", user=request.user):
        # New feature code
        pass

    # Use as a decorator
    @feature_flag("new_feature")
    def my_view(request):
        return {"message": "New feature enabled!"}
"""

default_app_config = "core.apps.CoreConfig"
