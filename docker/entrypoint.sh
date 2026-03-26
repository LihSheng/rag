#!/usr/bin/env bash
set -euo pipefail

python -m ragstack.bootstrap

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec uvicorn ragstack.api:app --host 0.0.0.0 --port 8000
