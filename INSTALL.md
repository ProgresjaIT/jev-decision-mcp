# Instalacja Jev Decision MCP na osobnym serwerze Ubuntu

Instrukcja dla wersji 1.0.0, sprawdzona 2026-11-25. Wszystkie polecenia produkcyjne
wykonuj przez SSH na **docelowym Ubuntu**, nie w WSL. Lokalne WSL służy tylko do
przeniesienia pakietu. Nie musisz korzystać ponownie z Codexa.

## 1. Wymagania

- Ubuntu 24.04 LTS lub 22.04 LTS, amd64/arm64, konto z sudo.
- Zalecane minimum dla samej usługi: 1 vCPU, 1 GB RAM (2 GB podczas budowy),
  3 GB wolnego dysku plus miejsce na historię i obrazy rollbacku. Bez GPU.
- Docker Engine + Compose v2 z obsługą `up --wait`, Python 3 do instalatora.
- Dostęp wychodzący HTTPS do rejestrów Docker/PyPI podczas budowy i
  `api.typesafe.ai:443` podczas pracy; DNS i poprawny czas systemowy.
- Ważny klucz z oficjalnej konsoli https://console.typesafe.ai.
- Dla zdalnego dostępu: własna domena z rekordem DNS, HTTPS przez reverse proxy,
  ewentualnie prywatny VPN. Endpoint MCP nigdy nie może być anonimowy.

Przed zmianą istniejącego serwera obejrzyj stan, nie zmieniaj cudzych usług:

```bash
uname -m
lsb_release -ds
free -h
df -h
sudo ss -ltnp
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

Ostatnie polecenie ma sens po instalacji Docker. Wybierz wolny port MCP i nazwę
wolumenu nieużywaną przez inną aplikację. Nie instaluj drugiego reverse proxy na
porcie zajętym przez istniejący serwer WWW; dodaj vhost w istniejącym proxy.

## 2. Docker i zależności na czystym Ubuntu

Jeżeli Docker i `docker compose version` już działają, pomiń instalację.
Na serwerze z produkcyjnymi kontenerami nie usuwaj pakietów ani nie restartuj
Dockera bez zaplanowanego okna. Poniższe polecenia dotyczą czystego Ubuntu.
Źródło: https://docs.docker.com/engine/install/ubuntu/.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg python3 python3-venv git unzip openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' \
  "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$(dpkg --print-architecture)" | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Skrypty możesz uruchamiać przez sudo. Alternatywnie dodaj swoje zaufane konto do
grupy docker (daje uprawnienia praktycznie równoważne root), potem wyloguj się
z SSH i zaloguj ponownie:

```bash
sudo usermod -aG docker "$USER"
```

Dalsze komendy zakładają dostęp do Docker bez sudo. Jeśli go nie masz, poprzedzaj
polecenia `docker` i skrypty usługowe przez sudo; `install.sh` uruchom jako zwykły
użytkownik, aby `.env` pozostał jego własnością.

## 3. Przeniesienie projektu

### ZIP przez SCP (zalecane dla dostarczonego pakietu)

W terminalu WSL, w katalogu z ZIP i sumą kontrolną:

```bash
read -r -p 'SSH użytkownik@serwer: ' TARGET
scp jev-decision-mcp.zip jev-decision-mcp.zip.sha256 "$TARGET:"
ssh "$TARGET"
```

Na docelowym Ubuntu:

```bash
sha256sum -c jev-decision-mcp.zip.sha256
mkdir -p "$HOME/services"
unzip -n jev-decision-mcp.zip -d "$HOME/services"
cd "$HOME/services/jev-decision-mcp"
chmod +x ./*.sh
```

`unzip -n` nie nadpisuje istniejących plików. Do aktualizacji rozpakuj nowy pakiet
w nowym katalogu, jak w punkcie 10; nie rozpakowuj go na działającą wersję.

### Git

Jeśli wcześniej umieściłeś projekt we własnym repozytorium:

```bash
read -r -p 'URL Twojego repozytorium: ' REPO_URL
mkdir -p "$HOME/services"
git clone "$REPO_URL" "$HOME/services/jev-decision-mcp"
cd "$HOME/services/jev-decision-mcp"
```

Repozytorium zdalne nie zostało utworzone automatycznie. `.env`, historia i klucze
nie mogą być śledzone przez Git.

## 4. Konfiguracja

```bash
./install.sh
chmod 600 .env
nano .env
```

`install.sh` tworzy `.env` tylko jeśli go nie ma i generuje mocny MCP_TOKEN.
Istniejącego pliku nigdy nie nadpisuje. Nie instaluje samodzielnie Dockera, nie
zmienia firewalla i nie uruchamia usługi. W razie przerwania można powtórzyć.

Ustaw:

| Zmienna | Znaczenie |
|---|---|
| TYPESAFE_API_KEY | oficjalny klucz TypeSafe; obowiązkowo uzupełnij |
| MCP_TOKEN | odrębny losowy sekret klientów MCP; minimum 32 znaki |
| MODEL | domyślnie przypięty `jev-1.14.0`; sprawdź dostępność na swoim koncie |
| MCP_PORT | wolny port hosta, np. 8765, publikowany tylko na 127.0.0.1 |
| PORT | port wewnątrz kontenera; ustawiony domyślnie, może być zmieniony |
| HOST | `0.0.0.0` wewnątrz kontenera; nie oznacza publicznego portu hosta |
| ALLOWED_HOSTS | `localhost,127.0.0.1,TWOJA-DOMENA` bez schematu i bez portu |
| DB_PATH | pozostaw `/data/history.sqlite3`, wewnątrz trwałego wolumenu |
| JEV_DATA_VOLUME | stała, unikalna nazwa wolumenu, zachowuj przy aktualizacjach |
| COMPOSE_PROJECT_NAME | stała nazwa projektu Compose, zachowuj przy aktualizacjach |
| TIMEOUT_SECONDS | całkowity limit oczekiwania na TypeSafe; domyślnie 20 |
| DAILY_BUDGET_USD | dzienny limit estymacji kosztów, dzień UTC |
| MAX_REQUEST_COST_USD | limit konserwatywnej rezerwacji pojedynczego wywołania |
| MAX_DAILY_CALLS | twardy lokalny limit liczby rozpoczętych wywołań na dobę |
| INPUT_USD_PER_MILLION / OUTPUT_USD_PER_MILLION | aktualne stawki swojego modelu |
| MIN_CONFIDENCE / MIN_PROBABILITY | progi Choice; Noul używa prawdopodobieństwa |
| NOUL_REJECT_THRESHOLD | próg odrzucenia Noul |
| SCORE_MIN_FRACTION | próg Score jako część skali, np. 0.75 |
| MAX_QUESTIONS / MAX_INPUT_BYTES | lokalne limity batch i rozmiaru danych |

Pozostałe zmienne mają opisane domyślne wartości w `.env.example`. Nie zmniejszaj
RESERVED_INPUT_TOKENS poniżej udokumentowanego limitu kontekstu modelu. Model,
taryfę i rezerwację zmieniaj razem. Nie edytuj konfiguracji za pośrednictwem agenta.
Nie uruchamiaj `docker compose config` na publicznym terminalu/logu: rozwija sekrety.
W razie potrzeby walidacji używaj `docker compose config --quiet`.

## 5. Budowa i uruchomienie

```bash
./start.sh
docker compose ps
./healthcheck.sh
./healthcheck.sh --api
```

Pierwszy skrypt buduje obraz, waliduje `.env`, uruchamia i czeka na healthcheck.
Ostatnia komenda wykonuje płatny syntetyczny test TypeSafe. Powinna pokazać
`tools: 10` i status `approved`. `requires_review` w lokalnym teście może oznaczać
brak klucza. API error zawsze wymaga wyjaśnienia.

Równoważne podstawowe polecenia:

```bash
docker compose build --pull jev
docker compose up -d --wait --wait-timeout 90 jev
docker compose logs --tail=100 jev
```

Na hoście adres to `http://127.0.0.1:WYBRANY_MCP_PORT/mcp`. Nie jest publiczny.
Nie wystawiaj portu przez `0.0.0.0:port:port` ani regułę przekierowania routera.

## 6. Automatyczny start i trwałość

Compose ustawia `restart: unless-stopped`. Docker uruchamia się przez systemd:

```bash
sudo systemctl enable docker
sudo systemctl is-enabled docker
docker compose ps
```

Po restarcie hosta kontener wraca automatycznie, chyba że wcześniej zatrzymałeś
go ręcznie. Wtedy użyj `docker compose up -d --wait`.
Baza i WAL są w nazwanym wolumenie, niezależnym od katalogu wydania i obrazu.
Nie używaj `docker compose down -v`, `docker volume prune` ani kasowania wolumenu.
`stop.sh` jedynie zatrzymuje proces.

## 7. HTTPS, firewall, uwierzytelnianie

### Wariant A: domena i Nginx na czystym serwerze

Rekord A/AAAA domeny musi wskazywać ten serwer. Jeżeli istnieje już reverse proxy,
dodaj do niego osobny vhost; nie wykonuj poniższej instalacji równolegle z innym
serwerem na 80/443. Przykład nie wyłącza istniejących vhostów.

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx ufw
read -r -p 'Domena MCP (np. jev.twoja-domena.pl): ' JEV_DOMAIN
read -r -p 'Port MCP z .env: ' JEV_PROXY_PORT
read -r -p 'Email administratora certyfikatu: ' CERT_EMAIL
# Tylko litery/cyfry/kropki/myślniki; port 1..65535:
[[ "$JEV_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || exit 1
[[ "$JEV_PROXY_PORT" =~ ^[0-9]+$ ]] && (( JEV_PROXY_PORT >= 1 && JEV_PROXY_PORT <= 65535 )) || exit 1
VHOST="/etc/nginx/sites-available/${JEV_DOMAIN}"
# Celowo odmowa nadpisania istniejącej konfiguracji:
sudo test ! -e "$VHOST" || { echo 'Vhost istnieje: dostosuj go ręcznie'; exit 1; }
sudo tee "$VHOST" >/dev/null <<NGINX
server {
    listen 80;
    server_name ${JEV_DOMAIN};
    client_max_body_size 256k;
    access_log off;
    location = /mcp {
        proxy_pass http://127.0.0.1:${JEV_PROXY_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header Authorization \$http_authorization;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_read_timeout 60s;
    }
    location / { return 404; }
}
NGINX
sudo ln -s "$VHOST" "/etc/nginx/sites-enabled/${JEV_DOMAIN}"
sudo nginx -t
sudo systemctl reload nginx
```

Przed `ufw enable` sprawdź rzeczywisty port SSH. Nie zakładaj portu 22 i nie
zamykaj aktywnej sesji do czasu sprawdzenia nowego logowania:

```bash
read -r -p 'Rzeczywisty port SSH: ' SSH_PORT
[[ "$SSH_PORT" =~ ^[0-9]+$ ]] || exit 1
sudo ufw allow "${SSH_PORT}/tcp"
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status verbose
sudo ufw enable
sudo certbot --nginx -d "$JEV_DOMAIN" --email "$CERT_EMAIL" --agree-tos --redirect
sudo certbot renew --dry-run
```

Nie otwieraj MCP_PORT. Docker potrafi omijać reguły UFW dla publikowanych portów;
bezpieczeństwo opiera się tu również na publikowaniu wyłącznie na loopback.
Dodaj domenę do ALLOWED_HOSTS w `.env`, potem:

```bash
docker compose up -d --wait --force-recreate jev
curl -s -o /dev/null -w '%{http_code}\n' "https://${JEV_DOMAIN}/mcp"
```

Bez tokenu oczekiwane **401**. Jeśli widzisz 200, przerwij konfigurację i sprawdź
routing. Nie wysyłaj Bearer przez nieszyfrowane HTTP przez Internet. Obecność
Bearer chroni endpoint, lecz token trzeba chronić jak hasło. Nie włączamy CORS;
żądania z nagłówkiem Origin są odrzucane. To integracja serwer-serwer.

Dodatkowo ogranicz 443 do sieci runtime OpenHands/VPN w firewallu chmurowym lub
regułach `allow/deny` Nginx, jeśli znasz stabilne adresy źródłowe. Zachowaj dostęp
ACME wymagany do odnawiania certyfikatu. Nie włączaj logowania Authorization.

### Wariant B: prywatny dostęp

Możesz zachować loopback i użyć tunelu SSH do testów:

```bash
# Na maszynie klienta, wartości dostosuj interaktywnie:
read -r -p 'SSH użytkownik@serwer: ' TARGET
read -r -p 'Port MCP na serwerze: ' REMOTE_MCP_PORT
read -r -p 'Wolny port lokalny tunelu: ' LOCAL_MCP_PORT
ssh -N -L "127.0.0.1:${LOCAL_MCP_PORT}:127.0.0.1:${REMOTE_MCP_PORT}" "$TARGET"
```

W drugim terminalu klient używa `http://127.0.0.1:PORT_TUNELU/mcp` i nadal Bearer.
Dla OpenHands w kontenerze localhost oznacza kontener. Tunel na hoście nie jest
sam z siebie osiągalny wewnątrz sandboxa. Dla trwałych automatyzacji użyj HTTPS
z osiągalnym DNS lub poprawnie skonfigurowanej prywatnej sieci i proxy.

## 8. OpenHands: gotowa konfiguracja

W aktualnym Agent Canvas: Customize → MCP Servers → Add custom server,
name `jev-decision`, typ `SHTTP`, URL `https://TWOJA-DOMENA/mcp`, Authentication
`Bearer token`, API Key = **MCP_TOKEN**, timeout 30. Kliknij Test connection:
10 narzędzi. Zapisz, otwórz nową rozmowę. Dołącz do wszystkich odpowiednich profili.

Dla SDK skopiuj poniższy wpis do istniejącej konfiguracji, podmieniając placeholdery:

```json
{
  "mcpServers": {
    "jev-decision": {
      "url": "https://TWOJA-DOMENA/mcp",
      "headers": {"Authorization": "Bearer WSTAW_MCP_TOKEN"}
    }
  }
}
```

W kodzie lepiej budować headers ze zmiennej środowiskowej, jak w
[examples/OPENHANDS.md](examples/OPENHANDS.md). Starszy format `shttp_servers`
jest w osobnym przykładzie. Nie zapisuj klucza TypeSafe w OpenHands: ma go tylko
serwer Jev. Testuj z tego samego runtime, z którego będą wychodzić połączenia.

Jeżeli narzędzia zapisujące mają być obowiązkowo walidowane, zastosuj
[docs/WRITE_GATE.md](docs/WRITE_GATE.md). Bez odcięcia bezpośredniej ścieżki zapisu
prompt nie wymusza kontroli. CRM utrzymaj read-only także w ACL i tokenach CRM.

## 9. Status, logi i pełny test klienta

```bash
docker compose ps
docker compose logs --since=10m --tail=100 jev
./healthcheck.sh
./healthcheck.sh --api
```

Test z osobnej maszyny, np. z runtime OpenHands (Python 3.12):

```bash
python3 -m venv .venv-client
.venv-client/bin/pip install 'mcp==2.3.0'
read -r -p 'Pełny HTTPS URL MCP: ' MCP_URL
read -r -s -p 'MCP token: ' MCP_TOKEN
printf '\n'
export MCP_URL MCP_TOKEN
.venv-client/bin/python examples/call_tools.py
# Opcjonalnie wszystkie przykłady: kilka płatnych, syntetycznych wywołań
.venv-client/bin/python examples/call_tools.py --all
unset MCP_TOKEN
```

Kod klienta pochodzi z tego projektu. Polecenie bez `--all` sprawdza tylko lokalną
kondycję i usage. Następnie w OpenHands rozpocznij nową rozmowę i poproś o
`health_check(check_api=true)` oraz `get_usage`. To końcowy test konkretnej instalacji.

## 10. Aktualizacja, restart, stop, rollback

Restart bez zmiany konfiguracji:

```bash
docker compose restart jev
./healthcheck.sh
```

Po edycji `.env` konieczne odtworzenie kontenera (sam restart nie wczyta env):

```bash
docker compose up -d --force-recreate --wait jev
```

Zatrzymanie: `./stop.sh`. Ponowny start: `docker compose up -d --wait jev`.

Aktualizacja przez Git, wyłącznie przy czystych plikach źródłowych:

```bash
git status --short
git pull --ff-only
./update.sh
```

Przy lokalnych zmianach najpierw je zachowaj; nie wykonuj reset --hard. Dla ZIP
rozpakuj nową wersję do świeżego katalogu, sprawdź sumę SHA256, skopiuj tam
**własny istniejący** `.env` z prawami 600, zachowując COMPOSE_PROJECT_NAME,
JEV_DATA_VOLUME i JEV_IMAGE. Przykład z interaktywnymi ścieżkami:

```bash
read -r -p 'Pełny katalog obecnego projektu: ' OLD_RELEASE
read -r -p 'Pełny nowy pusty katalog wydania: ' NEW_RELEASE
mkdir -p "$NEW_RELEASE"
unzip -n jev-decision-mcp.zip -d "$NEW_RELEASE"
install -m 600 "$OLD_RELEASE/.env" "$NEW_RELEASE/jev-decision-mcp/.env"
cd "$NEW_RELEASE/jev-decision-mcp"
chmod +x ./*.sh
./update.sh
```

Użyj rzeczywiście nowego katalogu; polecenie `install` powyżej ma przenieść własną
konfigurację, nie zastępować innego istniejącego środowiska.

`update.sh` zachowuje stary obraz pod tagiem rollback, tworzy spójną kopię SQLite
przez API backup, buduje nowy obraz i sprawdza healthcheck. Przy niepowodzeniu
uruchomienia automatycznie wraca do starego obrazu. `.env` nie jest nadpisywany.
Nie zmienia samodzielnie źródeł Git. Krótka przerwa przy wymianie pojedynczej
repliki jest normalna: planuj aktualizację poza aktywnymi zapisami.

Ręczny powrót do obrazu wymienionego w `backups/image-*.txt`:

```bash
ls backups/image-*.txt
read -r -p 'Tag obrazu rollback z wybranego pliku: ' ROLLBACK_IMAGE
JEV_IMAGE="$ROLLBACK_IMAGE" docker compose up -d --no-build --wait jev
./healthcheck.sh
```

Po rollbacku ustaw ten tag jako JEV_IMAGE w `.env`, żeby kolejny `up` go zachował.
Nie uruchamiaj `start.sh`, który buduje aktualne źródła pod skonfigurowanym tagiem,
zanim nie przywrócisz odpowiedniej wersji kodu. Nie usuwaj ostatniego dobrego obrazu.

Historia zazwyczaj pozostaje nowsza i nie wymaga cofnięcia. Jeżeli rzeczywiście
trzeba odtworzyć bazę, najpierw zachowaj aktualny wolumen i zatrzymaj usługę.
Odtworzenie usuwa późniejsze wpisy i może obniżyć licznik zużycia, więc traktuj je
jako operację awaryjną wymagającą świadomej decyzji. Wersja 1.0.0 nie zmienia schematu.
Przywracaj snapshot do **nowego wolumenu**, pozostawiając oryginał:

```bash
./stop.sh
read -r -p 'Ścieżka wybranej kopii SQLite: ' BACKUP_DB
read -r -p 'NOWA unikalna nazwa wolumenu: ' RESTORE_VOLUME
# Odmowa użycia istniejącego wolumenu:
if docker volume inspect "$RESTORE_VOLUME" >/dev/null 2>&1; then echo 'Wolumen istnieje; wybierz nowy'; exit 1; fi
docker volume create "$RESTORE_VOLUME"
docker run --rm --user 0 --entrypoint sh \
  -v "${RESTORE_VOLUME}:/restore" \
  -v "$(realpath "$BACKUP_DB"):/backup.sqlite3:ro" \
  "$ROLLBACK_IMAGE" -c 'cp /backup.sqlite3 /restore/history.sqlite3 && chown 10001:10001 /restore/history.sqlite3 && chmod 600 /restore/history.sqlite3'
```

W `.env` ustaw JEV_DATA_VOLUME na nową nazwę i JEV_IMAGE na tag rollback, a potem
`docker compose up -d --no-build --wait jev`. Oryginalny wolumen pozostał nietknięty.
Kopie z `backups/` przechowuj dodatkowo poza serwerem z ograniczonym dostępem.

## 11. Rozwiązywanie problemów

| Objaw | Działanie |
|---|---|
| 401 na MCP | Sprawdź MCP_TOKEN w OpenHands; nie używaj klucza TypeSafe. Sprawdź przekazywanie Authorization przez proxy. |
| TypeSafeAuthenticationError | Klucz nie działa na oficjalnym API. Wygeneruj klucz w konsoli TypeSafe; ustaw TYPESAFE_API_KEY i odtwórz kontener. |
| 400 Invalid host header | Dodaj domenę do ALLOWED_HOSTS bez schematu/portu; recreate. Nie ustawiaj `*`. |
| 403 browser_origin_forbidden | Użyj klienta serwerowego MCP. Nie wywołuj endpointu przez skrypt w przeglądarce. |
| Timeout / connection refused | Sprawdź DNS, proxy, firewall i dostęp z runtime OpenHands. localhost w kontenerze to nie host. |
| Port zajęty | `sudo ss -ltnp`; wybierz wolny MCP_PORT i popraw proxy. |
| budget_or_call_limit | get_usage, limity UTC i rezerwacje błędów. Nie usuwaj bazy, by omijać limit. Poczekaj lub świadomie zwiększ limit. |
| TypeSafeRateLimitError / 429 / 529 | Zmniejsz częstotliwość automatyzacji. Brak automatycznych retry celowo ogranicza koszt. |
| requires_review | To może być prawidłowa niepewna ocena. Uzupełnij dowody lub przekaż człowiekowi; nie obniżaj progu dla pojedynczego wyniku. |
| unhealthy bez klucza | Uzupełnij TYPESAFE_API_KEY; healthcheck nie udaje sprawnej integracji. |
| SQLite readonly / permission denied | Sprawdź wolumen /data i UID 10001. Nie montuj katalogu hosta bez poprawnych praw. |
| Narzędzia niewidoczne | Nowa rozmowa, właściwy profil, Test connection, oczekiwane 10 narzędzi. |
| Brak Docker Compose | Zainstaluj docker-compose-plugin; używaj `docker compose`, nie starego `docker-compose`. |
| Sekrety odrzucone / personal_data_in_question | Usuń wrażliwe pola i PII z pytań/opcji; nie wyłączaj filtra. |

Nie publikuj pełnego `.env`, `docker inspect` ani rozwiniętego Compose w zgłoszeniu.
Bezpieczne logi aplikacji zawierają kody błędów, nie treści klientów. Test z mockami
nie potwierdza produkcyjnego dostępu TypeSafe ani integracji z konkretnym OpenHands.
