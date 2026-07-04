"""Custom parsers for Django Ninja using orjson for performance."""

from typing import Any

import orjson
from ninja.parser import Parser


class ORJSONParser(Parser):
    """High-performance JSON parser using orjson."""

    def parse_body(self, request) -> Any:
        return orjson.loads(request.body)
