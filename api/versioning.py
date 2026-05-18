"""API versioning support.

Pattern: mount NinjaExtraAPI instances at versioned URL prefixes.

    urlpatterns = [
        path("api/v1/", api_v1.urls),
        path("api/v2/", api_v2.urls),
    ]

Controllers can be registered on one or both versions. V2-only changes
are added to api_v2 without touching api_v1. Shared controllers go on
both instances via register_controllers().

Migration guide
---------------
- Breaking changes go in v2 only; v1 stays frozen.
- Deprecate a v1 endpoint by adding a Deprecation header in the response.
- Remove a v1 endpoint after the grace period by unregistering its controller.
"""

from ninja_extra import NinjaExtraAPI

api_v1 = NinjaExtraAPI(
    version="1.0",
    title="Django Ninja Boilerplate API v1",
    description="Stable API - breaking changes will appear in v2",
    urls_namespace="api_v1",
    openapi_extra={"info": {"termsOfService": "https://example.com/terms/"}},
)

api_v2 = NinjaExtraAPI(
    version="2.0",
    title="Django Ninja Boilerplate API v2",
    description="Next API version — may contain breaking changes from v1",
    urls_namespace="api_v2",
    openapi_extra={"info": {"termsOfService": "https://example.com/terms/"}},
)
