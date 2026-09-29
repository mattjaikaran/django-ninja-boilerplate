#!/usr/bin/env bash

# Generate a per-install Centrifugo JWT signing secret.

set -euo pipefail

if [ ! -f .env ]; then
    echo ".env does not exist. Run the setup command first." >&2
    exit 1
fi

existing_secret=$(grep -E '^CENTRIFUGO_TOKEN_SECRET=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "'\"")
case "$existing_secret" in
    "" | centrifugo-token-secret | dev-centrifugo-token-secret) ;;
    *)
        echo "CENTRIFUGO_TOKEN_SECRET is already set; leaving it unchanged."
        exit 0
        ;;
esac

if command -v python3 >/dev/null 2>&1; then
    secret=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
elif command -v openssl >/dev/null 2>&1; then
    secret=$(openssl rand -hex 32)
else
    echo "Python3 or OpenSSL is required to generate the secret." >&2
    exit 1
fi

python3 - "$secret" <<'PY'
import pathlib
import sys

secret = sys.argv[1]
path = pathlib.Path(".env")
lines = path.read_text().splitlines()
setting = f"CENTRIFUGO_TOKEN_SECRET={secret}"
for index, line in enumerate(lines):
    if line.startswith("CENTRIFUGO_TOKEN_SECRET="):
        lines[index] = setting
        break
else:
    lines.append(setting)
path.write_text("\n".join(lines) + "\n")
PY

echo "Wrote CENTRIFUGO_TOKEN_SECRET to .env."
