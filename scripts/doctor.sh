#!/bin/bash
# Environment preflight for Django Ninja Boilerplate.
# Run with: just doctor or ./scripts/doctor.sh
# The checks live in scripts/doctor.py (stdlib only, no venv needed).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/doctor.py "$@"
