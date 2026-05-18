"""SSE ASGI view — authenticated streaming endpoint.

Mount in urls.py:

    from core.sse.views import sse_endpoint

    urlpatterns = [
        ...
        path("api/events/stream/", sse_endpoint),
    ]

Clients connect with a JWT token in the query string because browsers
can't set Authorization headers on EventSource connections:

    const es = new EventSource("/api/events/stream/?token=<jwt>");
"""

import logging

from django.http import StreamingHttpResponse
from ninja_jwt.tokens import AccessToken

from core.sse.events import sse_stream

logger = logging.getLogger(__name__)


def sse_endpoint(request):
    """Stream SSE events for the authenticated user.

    Accepts ?token=<jwt> because browsers cannot set Authorization headers
    on native EventSource connections.

    Returns a StreamingHttpResponse with Content-Type text/event-stream.
    """
    token_str = request.GET.get("token", "")
    if not token_str:
        from django.http import HttpResponse

        return HttpResponse("Missing token", status=401)

    try:
        token = AccessToken(token_str)
        user_id = token.get("user_id")
    except Exception:
        from django.http import HttpResponse

        return HttpResponse("Invalid token", status=401)

    channel = f"user:{user_id}"

    response = StreamingHttpResponse(
        sse_stream(channel),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
