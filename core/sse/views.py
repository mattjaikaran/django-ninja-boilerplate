"""SSE ASGI view — authenticated streaming endpoint.

Mount in urls.py:

    from core.sse.views import sse_endpoint

    urlpatterns = [
        ...
        path("api/events/stream/", sse_endpoint),
    ]

Clients authenticate with the HttpOnly access cookie:

    const es = new EventSource("/api/events/stream/", {withCredentials: true});
"""

import logging

from django.http import HttpResponse, StreamingHttpResponse
from ninja_jwt.exceptions import AuthenticationFailed, InvalidToken
from core.security.cookie_auth import CookieJWTAuth

from core.sse.events import sse_stream

logger = logging.getLogger(__name__)


def sse_endpoint(request):
    """Stream SSE events for the authenticated user.

    Uses the same cookie-only JWT verification as application controllers.

    Returns a StreamingHttpResponse with Content-Type text/event-stream.
    """
    try:
        user = CookieJWTAuth()(request)
    except (AuthenticationFailed, InvalidToken):
        return HttpResponse("Invalid authentication cookie", status=401)
    if not user:
        return HttpResponse("Missing authentication cookie", status=401)
    channel = f"user:{user.id}"

    response = StreamingHttpResponse(
        sse_stream(channel),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
