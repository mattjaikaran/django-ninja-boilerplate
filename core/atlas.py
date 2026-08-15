"""Atlas metadata for the core app.

The atlas generator reads this module to fill the prose on the map blocks.
The ``what`` line answers "what does it do", the ``how`` line answers
"how is it built", and ``children`` describes the inside view. Adopters
add an identical ``atlas.py`` to each of their apps.
"""

ATLAS = {
    "code": "CR",
    "name": "Core",
    "what": (
        "Users, authentication, and platform services: JWT login, magic "
        "links, OTP, API keys, 2FA, audit logging, feature flags, emails, "
        "and the observability stack."
    ),
    "how": (
        "Controller classes in core/controllers delegate to services in "
        "core/services. Base models (SoftDeleteModel), base services "
        "(CRUDService), and shared decorators all live here."
    ),
    "children": {
        "controllers": {
            "name": "Auth & Users",
            "what": "JWT, magic links, OTP, API keys, audit",
        },
        "services": {
            "name": "Services",
            "what": "Business logic, email, OTP, base services",
        },
        "models": {
            "name": "Models",
            "what": "User, OTP, API key, audit log, base models",
        },
        "schemas": {"name": "Schemas", "what": "Pydantic request/response schemas"},
        "admin": {
            "name": "Admin",
            "what": "Unfold admin configs and dashboard callback",
        },
    },
}
