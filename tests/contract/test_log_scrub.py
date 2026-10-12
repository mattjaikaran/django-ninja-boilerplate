"""Contract: every credential-shaped request field is masked before logging.

`log_api_call(include_payload=True)` logs request bodies. A new schema field
that holds a secret (`newPassword`, `otpCode`, `refresh`) must not reach the
log in plain text, so walk the OpenAPI request bodies and check each one.
"""

import re

from api.decorators import _scrub
from api.urls import api

#: Name words that mark a credential, matched on the snake_case field name.
CREDENTIAL_NAME = re.compile(
    r"(^|_)(password\d?|passcode|token|secret|otp|totp|code|pin|cvv|ssn"
    r"|authorization|cookie|session|refresh)(_|$)"
    r"|(api|private|secret)_?key|card_?number"
)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).replace("-", "_").lower()


def _request_body_property_names(schema: dict) -> set[str]:
    components = schema.get("components", {}).get("schemas", {})
    names: set[str] = set()

    def walk(node: object, seen: frozenset[str]) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                target = ref.rsplit("/", 1)[-1]
                if target not in seen:
                    walk(components.get(target, {}), seen | {target})
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.update(properties)
            for value in node.values():
                walk(value, seen)
        elif isinstance(node, list):
            for item in node:
                walk(item, seen)

    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "requestBody" in operation:
                walk(operation["requestBody"], frozenset())
    return names


def test_every_credential_request_field_is_scrubbed():
    names = _request_body_property_names(api.get_openapi_schema())
    credentials = sorted(n for n in names if CREDENTIAL_NAME.search(_snake(n)))
    assert credentials, "regex matched no request fields; the walk is broken"

    leaked = [n for n in credentials if _scrub({n: "x"}) != {n: "***"}]
    assert not leaked, f"request fields logged in plain text: {leaked}"


def test_nested_dicts_and_lists_are_scrubbed():
    payload = {
        "user": {"newPassword": "hunter2", "name": "a"},
        "devices": [{"otpCode": "123456"}, {"sessionId": "s"}],
    }

    assert _scrub(payload) == {
        "user": {"newPassword": "***", "name": "a"},
        "devices": [{"otpCode": "***"}, {"sessionId": "***"}],
    }
