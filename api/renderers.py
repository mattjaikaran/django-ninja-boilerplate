"""Custom renderers for Django Ninja using orjson for performance."""

from decimal import Decimal
from typing import Any

import orjson
from ninja.renderers import BaseRenderer


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type is not JSON serializable: {type(obj)}")


class ORJSONRenderer(BaseRenderer):
    """High-performance JSON renderer using orjson.

    2-10x faster than stdlib json. Natively handles datetime, UUID,
    dataclass, and numpy types without custom encoders.
    """

    media_type = "application/json"

    def render(self, request, data: Any, *, response_status: int) -> bytes:
        return orjson.dumps(
            data,
            default=_default,
            option=orjson.OPT_NON_STR_KEYS
            | orjson.OPT_SERIALIZE_NUMPY
            | orjson.OPT_NAIVE_UTC
            | orjson.OPT_UTC_Z,
        )
