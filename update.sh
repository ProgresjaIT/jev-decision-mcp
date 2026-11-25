#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
umask 077
# New source is supplied by the operator; no destructive git reset or secret overwrite.
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
container=$(docker compose ps -q jev)
[[ -n "$container" ]] || { echo 'Usługa nie działa; użyj start.sh.' >&2; exit 1; }
old_image=$(docker inspect --format '{{.Image}}' "$container")
backup_image="jev-decision-mcp:rollback-${stamp}"
docker tag "$old_image" "$backup_image"
printf '%s\n' "$backup_image" > "backups/image-${stamp}.txt"
# SQLite online backup includes committed WAL data without pausing the service.
docker compose exec -T jev python -c 'import os, sqlite3; src=sqlite3.connect(os.environ["DB_PATH"]); dst=sqlite3.connect("/tmp/history-backup.sqlite3"); src.backup(dst); dst.close(); src.close()'
docker cp "${container}:/tmp/history-backup.sqlite3" "backups/history-${stamp}.sqlite3"
docker compose build --pull jev
if ! docker compose up -d --wait --wait-timeout 90 jev || ! ./healthcheck.sh; then
    echo 'Aktualizacja nie przeszła testu. Przywracanie poprzedniego obrazu.' >&2
    JEV_IMAGE="$backup_image" docker compose up -d --no-build --wait --wait-timeout 90 jev
    exit 1
fi
echo "Zaktualizowano. Obraz do rollbacku: ${backup_image}. Kopia bazy: backups/history-${stamp}.sqlite3"
