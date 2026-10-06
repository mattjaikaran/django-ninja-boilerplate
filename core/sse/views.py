"""SSE ASGI view — authenticated streaming endpoint.

Mount in urls.py:

    from core.sse.views import sse_endpoint

    urlpatterns = [
        ...
        path("api/events/stream/", sse_endpoint),
    ]

Browser clients on the cookie contract (docs/COOKIE_AUTH.md) connect with
``new EventSource("/api/events/stream/", { withCredentials: true })`` and the
httpOnly access cookie authenticates them. Other clients pass the JWT in the
query string because EventSource cannot set an Authorization header:

    const es = new EventSource("/api/events/stream/", {withCredentials: true});
"""

import logging

from django.conf import settings
from django.core.handlers.asgi import ASGIRequest
from django.http import StreamingHttpResponse
from ninja_jwt.tokens import AccessToken

from core.sse.events import sse_stream, sse_stream_async

logger = logging.getLogger(__name__)


def sse_endpoint(request):
    """Stream SSE events for the authenticated user.

    Reads the JWT from ``?token=`` or, failing that, the access cookie,
    because browsers cannot set Authorization headers on native EventSource
    connections.

    Returns a StreamingHttpResponse with Content-Type text/event-stream.
    """
    token_str = request.GET.get("token") or request.COOKIES.get(
        settings.AUTH_COOKIE_ACCESS_NAME, ""
    )
    if not token_str:
        from django.http import HttpResponse

        return HttpResponse("Missing token", status=401)

    try:
        user = CookieJWTAuth()(request)
    except (AuthenticationFailed, InvalidToken):
        return HttpResponse("Invalid authentication cookie", status=401)
    if not user:
        return HttpResponse("Missing authentication cookie", status=401)
    channel = f"user:{user.id}"

    # Production serves ASGI (Gunicorn + uvicorn workers), which needs an async
    # iterator; the WSGI dev server needs a sync one.
    stream = (
        sse_stream_async(channel)
        if isinstance(request, ASGIRequest)
        else sse_stream(channel)
    )
    # Under ASGI, GZipMiddleware compresses each chunk as a separate gzip
    # member; httpx, for one, decodes only the first, so every event after
    # "connected" is lost. The middleware reads Accept-Encoding after the view
    # returns; drop it so the stream goes out uncompressed.
    request.META.pop("HTTP_ACCEPT_ENCODING", None)
    response = StreamingHttpResponse(stream, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
