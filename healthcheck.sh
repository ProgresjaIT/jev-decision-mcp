#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
args=()
if [[ "${1:-}" == '--api' ]]; then args=(-e CHECK_API=1); fi
docker compose exec -T "${args[@]}" jev python -m jev_decision.probe
