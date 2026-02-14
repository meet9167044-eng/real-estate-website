#!/usr/bin/env bash
set -e

# Ensure packaging tools are available in the runtime environment
python -m pip install --upgrade pip setuptools wheel

# Start gunicorn using the same Python interpreter and bind to Render's $PORT
exec python -m gunicorn app:app --bind 0.0.0.0:${PORT:-8000}
