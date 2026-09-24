#!/usr/bin/env bash
# Print a controller skeleton that matches the repo conventions.
#
# Usage: ./scaffold_controller.sh <app> <Resource>
# Example: ./scaffold_controller.sh billing Invoice
#
# This prints to stdout. Review the output, then write it to
# <app>/controllers/<resource>_controller.py yourself.

set -euo pipefail

app="${1:-}"
resource="${2:-}"

if [[ -z "$app" || -z "$resource" ]]; then
  echo "usage: $0 <app> <Resource>" >&2
  exit 1
fi

module="$(printf '%s' "$resource" | tr '[:upper:]' '[:lower:]')"
plural="$(printf '%s' "$module" | sed 's/y$/ies/; t; s/$/s/')"

cat <<PY
"""${resource} controller — HTTP adapter only.

Route prefix: /${plural}. Business logic lives in ${resource}Service.
"""

import logging

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call, validate_request
from ${app}.schemas import (
    Create${resource}Schema,
    ${resource}Schema,
    Update${resource}Schema,
)
from ${app}.services import ${resource}Service

logger = logging.getLogger(__name__)


@api_controller("/${plural}", tags=["${resource}s"], auth=JWTAuth())
class ${resource}Controller:
    def __init__(self) -> None:
        self.service = ${resource}Service()

    @http_get("/", response={200: list[${resource}Schema], 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_${plural}(self, request):
        return 200, self.service.list_for_user(request.user)

    @http_get("/{item_id}", response={200: ${resource}Schema, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def get_${module}(self, request, item_id: str):
        return 200, self.service.get(item_id, request.user)

    @http_post("/", response={201: ${resource}Schema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_${module}(self, request, payload: Create${resource}Schema):
        return 201, self.service.create(payload, request.user)

    @http_put("/{item_id}", response={200: ${resource}Schema, 404: dict, 500: dict})
    @log_api_call(include_payload=True)
    @handle_exceptions()
    def update_${module}(self, request, item_id: str, payload: Update${resource}Schema):
        return 200, self.service.update(item_id, payload, request.user)

    @http_delete("/{item_id}", response={204: None, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_${module}(self, request, item_id: str):
        self.service.delete(item_id, request.user)
        return 204, None
PY
