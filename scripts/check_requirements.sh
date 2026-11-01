#!/usr/bin/env bash
# Fail if requirements.txt is out of sync with uv.lock. Only the header comment
# is ignored, since it records the command line that generated the file.
if ! diff <(uv export --quiet --frozen --no-emit-project --no-hashes \
        --no-default-groups --group app | grep -v '^#') \
    <(grep -v '^#' requirements.txt); then
    echo "requirements.txt is stale. Regenerate it with:" >&2
    echo "  uv export --no-emit-project --no-hashes --no-default-groups --group app -o requirements.txt" >&2
    exit 1
fi
