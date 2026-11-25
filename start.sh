#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
test -f .env || { echo 'Najpierw ./install.sh' >&2; exit 1; }
docker compose build --pull jev
# Validates configuration without printing credentials or starting the server.
docker compose run --rm --no-deps --entrypoint python jev -m jev_decision.server --check-config
docker compose up -d --wait --wait-timeout 90 jev
./healthcheck.sh
