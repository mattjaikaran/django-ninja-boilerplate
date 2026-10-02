"""Test tokens remain usable when local environment keys are blank or unrelated."""

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("local_signing_key", ["", "unrelated-local-signing-key"])
def test_access_tokens_ignore_local_environment_keys(local_signing_key: str) -> None:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "api.settings.test",
        "NINJA_JWT_SIGNING_KEY": local_signing_key,
        "ENVIRONMENT": "development",
        "DJANGO_ENVIRONMENT": "development",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
import django
import jwt

django.setup()
from django.conf import settings
from ninja_jwt.tokens import AccessToken

encoded = str(AccessToken())
restored = AccessToken(encoded)
try:
    jwt.decode(encoded, settings.SECRET_KEY, algorithms=["HS256"])
except jwt.InvalidSignatureError:
    django_key_accepted = False
else:
    django_key_accepted = True
print(json.dumps({"token_type": restored["token_type"], "django_key_accepted": django_key_accepted}))
""",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout.splitlines()[-1]) == {
        "token_type": "access",
        "django_key_accepted": False,
    }
