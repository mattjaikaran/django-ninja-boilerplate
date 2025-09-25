#!/bin/bash

# lint.sh - Legacy script updated to use ruff

# Check if uv is available, otherwise fall back to direct ruff execution
if command -v uv &> /dev/null; then
    echo "Running linting with ruff via uv..."
    uv run ruff check .
    uv run ruff format .
else
    echo "uv not found, running ruff directly..."
    ruff check .
    ruff format .
fi