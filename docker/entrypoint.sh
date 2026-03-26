#!/usr/bin/env bash
set -euo pipefail

python -m ragstack.bootstrap

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec sleep infinity

