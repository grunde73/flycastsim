#!/usr/bin/env bash
# Fail on known vulnerabilities in the locked dependencies. `uv audit` can exit
# 0 with findings (seen in uv 0.10.12), so its summary line is checked as well.
out=$(uv audit --frozen 2>&1)
status=$?
if [ "$status" -ne 0 ] || ! grep -q '^Found no known vulnerabilities' <<<"$out"; then
    echo "$out"
    exit 1
fi
