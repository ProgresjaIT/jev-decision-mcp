#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
umask 077
command -v python3 >/dev/null || { echo 'Zainstaluj python3 zgodnie z INSTALL.md' >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.env')
if not p.exists():
    text=Path('.env.example').read_text().replace('MCP_TOKEN=\n','MCP_TOKEN='+secrets.token_urlsafe(48)+'\n')
    with p.open('x') as f: f.write(text)
    p.chmod(0o600)
    print('Utworzono .env. Uzupełnij TYPESAFE_API_KEY. Token MCP wygenerowany.')
else:
    print('Zachowano istniejący .env bez zmian.')
PY
command -v docker >/dev/null || { echo 'Brak Docker. Wykonaj instrukcję instalacji w INSTALL.md.' >&2; exit 1; }
docker compose version
echo 'Środowisko przygotowane. Po edycji .env uruchom ./start.sh'
