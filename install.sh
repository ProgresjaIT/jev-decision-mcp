#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
umask 077
command -v python3 >/dev/null || { echo 'Zainstaluj python3 zgodnie z INSTALL.md' >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import re
import secrets
p=Path('.env')
original=p.read_text() if p.exists() else None
text=original if original is not None else Path('.env.example').read_text()
defaults={
    'MCP_TOKEN': secrets.token_urlsafe(48),
    'HOST': '0.0.0.0',
    'DB_PATH': '/data/history.sqlite3',
    'COMPOSE_PROJECT_NAME': 'jev-decision',
}
for key, value in defaults.items():
    pattern=rf'(?m)^[ \t]*(?:export[ \t]+)?{key}[ \t]*=([^\n]*)'
    matches=list(re.finditer(pattern, text))
    if not matches:
        text=text.rstrip('\n')+'\n'+key+'='+value+'\n'
    elif key == 'MCP_TOKEN' and matches[-1].group(1).strip() in ('', '""', "''"):
        match=matches[-1]
        text=text[:match.start()]+key+'='+value+text[match.end():]
if text != original:
    with p.open('x' if original is None else 'w') as f: f.write(text)
p.chmod(0o600)
print('Konfiguracja gotowa. Uzupełnij tylko TYPESAFE_API_KEY; pozostałe ustawienia są automatyczne.')
PY
command -v docker >/dev/null || { echo 'Brak Docker. Wykonaj instrukcję instalacji w INSTALL.md.' >&2; exit 1; }
docker compose version
echo 'Środowisko przygotowane. Po edycji .env uruchom ./start.sh'
