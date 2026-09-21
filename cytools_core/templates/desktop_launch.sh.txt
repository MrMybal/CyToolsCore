#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$ROOT/runtime/python/bin/python" "$ROOT/app/desktop.py" "$@"
