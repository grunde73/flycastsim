#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync -U
uv export --no-emit-project --no-hashes --no-default-groups --group app \
    -o requirements.txt
