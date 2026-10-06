#!/usr/bin/env bash
# Generate secrets with scripts/env_secrets.py.
#
#   ./scripts/generate_secret_key.sh               print one new SECRET_KEY,
#                                                  for a secret store
#   ./scripts/generate_secret_key.sh --update-env  generate the unset secrets
#                                                  in .env; prints names only
#
# --update-env never replaces a value you set: a new SECRET_KEY invalidates
# sessions and JWTs, and a value may come from a secret store.

set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)

case "${1:-}" in
    --update-env)
        exec python3 "$script_dir/env_secrets.py" fill
        ;;
    "")
        python3 - "$script_dir" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
import env_secrets

print(env_secrets.generate(env_secrets.SECRETS[0]))
PY
        ;;
    -h | --help)
        sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
        ;;
    *)
        echo "Unknown option: $1 (see --help)" >&2
        exit 1
        ;;
esac
