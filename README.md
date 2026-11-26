# Jev Decision MCP

Serwer MCP w Pythonie do ocen, klasyfikacji i wyboru działań przez TypeSafe Jev. Udostępnia 10 narzędzi opartych na Choice, Score i Noul z oficjalnego `typesafe-sdk`.

JEV ocenia przekazany kontekst i zwraca wynik wraz z prawdopodobieństwem oraz statusem. `validate_action` sprawdza zgodność działania i ryzyko w jednym zapytaniu. `batch_decisions` wykonuje kilka ocen ze wspólnym kontekstem w jednym zapytaniu.

Serwer przechowuje lokalną historię użycia w SQLite i pilnuje skonfigurowanych limitów kosztów oraz liczby wywołań. Oceny są doradcze. Serwer sam nie wykonuje ocenianych działań i nie zapisuje zmian w zewnętrznych aplikacjach.

Instalacja kontenerowa: [Docker — krok po kroku](#instalacja-w-dockerze--krok-po-kroku), w tym wariant dla `mcp-proxy` i diagnostyka `Connection closed`.

## Instalacja (PowerShell)

Wymagane: uv oraz Python 3.12+ (uv może go pobrać).

```powershell
cd C:\Users\User\Documents\GitHub\jev-decision-mcp
uv sync --python 3.12
```

W hoście MCP (np. AgentDashboard) ustaw **tylko jeden sekret** procesu serwera:

```dotenv
TYPESAFE_API_KEY=twoj_klucz_typesafe
```

Pozostałe ustawienia mają wartości domyślne. Model to `jev-1.14.0`. Nie potrzeba klucza OpenAI, przeglądarki ani Dockera do uruchomienia w hoście MCP.

W domyślnym trybie stdio serwer korzysta ze zmiennych środowiskowych przekazanych przez hosta i nie odczytuje `.env`. `.env.example` zawiera wyłącznie `TYPESAFE_API_KEY`. Klucz wpisz w polu sekretów hosta, nie w argumentach narzędzi. Samo zapisanie klucza w pliku na dysku nie wystarczy.

Brak klucza nie blokuje wykrycia narzędzi, ale lokalny `health_check` zwraca `requires_review`, a oceny nie zostają zatwierdzone. Konto TypeSafe musi mieć dostęp do skonfigurowanego modelu.

Na Linuksie instalacja jest taka sama; interpreter środowiska znajduje się w `.venv/bin/python`.

## Konfiguracja klienta MCP

Po instalacji najprościej uruchamiać bezpośrednio interpreter środowiska:

```json
{
  "mcpServers": {
    "jev-decision": {
      "command": "C:/Users/User/Documents/GitHub/jev-decision-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "jev_decision.server"]
    }
  }
}
```

Dla klienta z konfiguracją TOML:

```toml
[mcp_servers.jev-decision]
command = "C:/Users/User/Documents/GitHub/jev-decision-mcp/.venv/Scripts/python.exe"
args = ["-m", "jev_decision.server"]
env_vars = ["TYPESAFE_API_KEY"]
```

`env_vars` przekazuje zmienne dostępne w środowisku hosta. Host musi otrzymać klucz przed uruchomieniem serwera. W AgentDashboard użyj konfiguracji environment/secrets danego serwera.

Alternatywnie:

```powershell
uv run --directory C:/Users/User/Documents/GitHub/jev-decision-mcp jev-decision-mcp
```

To domyślnie serwer **stdio**: oczekuje komunikatów MCP na standardowym wejściu i odpowiada na standardowym wyjściu. Nie otwiera okna ani konsoli interaktywnej. Nie został automatycznie dopisany do konfiguracji żadnego klienta.

Jeśli host używa `mcp-proxy` i `stdio_client`, uruchamiaj powyższe polecenie bez `--transport http`. Proces HTTP nie odpowiada na inicjalizację stdio; zakończenie procesu może być widoczne jako `McpError: Connection closed`. Dokładny powód zakończenia sprawdź we wcześniejszych logach stderr serwera.

## Narzędzia

| Narzędzie | Działanie |
|---|---|
| `make_decision` | Wybiera jedną z podanych opcji przez Choice |
| `evaluate_condition` | Ocenia prawdziwość warunku przez Noul |
| `score_quality` | Ocenia jakość na uporządkowanej skali Score |
| `evaluate_risk` | Klasyfikuje ryzyko: low, medium, high, critical |
| `compare_options` | Porównuje podane alternatywy przez Choice |
| `classify_data` | Przypisuje jedną z podanych kategorii |
| `validate_action` | Sprawdza zgodność działania i jego ryzyko |
| `batch_decisions` | Wykonuje kilka ocen w jednym zapytaniu |
| `get_usage` | Zwraca lokalne zużycie i estymację kosztów |
| `health_check` | Sprawdza konfigurację i bazę; opcjonalnie API |

Przykładowe argumenty `make_decision`:

```json
{
  "context": {
    "posts_reviewed": 100,
    "false_matches": 30,
    "rollback_available": true
  },
  "goal": "Poprawić trafność dopasowań",
  "criteria": "Najpierw sprawdzić zmianę na odrębnym zbiorze danych",
  "options": {
    "keep": "Pozostawić obecną konfigurację",
    "test": "Przetestować nową konfigurację",
    "review": "Zebrać dodatkowe dane"
  }
}
```

`context`, `goal`, `criteria` i `options` są wymagane dla tego narzędzia. Kontekst może być tekstem, obiektem lub listą. Dodawaj opcję braku działania albo braku danych. Wszystkie przykłady: [examples/tools.json](examples/tools.json).

Odpowiedź oceny zawiera `decision_id`, `status`, `meets_thresholds`, `results`, `elapsed_ms`, `model`, `usage`, `estimated_cost_usd` i `cost_source`. Status to `approved`, `rejected`, `requires_review` lub `error`. Nieprawidłowe argumenty mogą zostać odrzucone wcześniej jako błąd protokołu MCP.

`approved` oznacza przejście skonfigurowanych progów. W Choice dotyczy pewności wyboru, także gdy wybrana opcja oznacza rezygnację z działania. Nie jest uprawnieniem do zapisu. `requires_review` i `error` powinny blokować automatyczne wykonanie działania.

Domyślnie Choice wymaga confidence co najmniej 0.8 i prawdopodobieństwa co najmniej 0.9. Noul zatwierdza od 0.9, odrzuca do 0.1, a pozostałe wyniki wymagają przeglądu. Score przyjmuje 2–10 opisowych poziomów od najgorszego do najlepszego; próg wynosi 0.75 zakresu skali. Ocena ryzyka zatwierdza tylko dostatecznie pewne `low`.

## Limity i przechowywanie danych

Domyślny timeout zapytania TypeSafe wynosi 20 sekund. Serwer nie ponawia automatycznie zapytań. Limit batch to 32 pytania, a limit wejścia to 65536 bajtów.

Domyślny budżet to 1 USD na dobę UTC, limit rezerwacji jednego zapytania to 0.01 USD, a limit liczby rozpoczętych wywołań to 1000 na dobę. Koszt jest estymacją z lokalnych stawek, nie rachunkiem dostawcy. Rezerwacja obejmuje po 65536 tokenów wejścia i wyjścia; domyślne stawki wynoszą odpowiednio 0.042 i 0 USD za milion. Przy zmianie modelu sprawdź i dostosuj stawki oraz rezerwację. Nieznany koszt po błędzie zachowuje rezerwację budżetu.

W trybie stdio baza znajduje się w `~/.local/share/jev-decision/history.sqlite3`, w katalogu użytkownika uruchamiającego serwer. Opcjonalne `DB_PATH` zmienia tę lokalizację. W hoście z nietrwałym systemem plików wskaż trwały katalog, aby historia i liczniki przetrwały odtworzenie środowiska.

SQLite przechowuje metadane wywołań, statusy i zużycie, bez kontekstu, odpowiedzi i kluczy API. Dane przekazane do oceny trafiają do TypeSafe. Filtr rozpoznanych sekretów i danych osobowych jest ograniczony; minimalizuj i anonimizuj kontekst przed wywołaniem.

Opcjonalne ustawienia modelu, progów i budżetów są zdefiniowane w [config.py](src/jev_decision/config.py). Nie trzeba dodawać ich do pól sekretów podczas instalacji.

## Instalacja w Dockerze — krok po kroku

### 1. Wybierz sposób połączenia

| Konfiguracja hosta MCP | Wariant |
|---|---|
| Podajesz URL i nagłówek Authorization | **HTTP przez Docker Compose**, kroki 2–6 |
| Podajesz command/args, a host uruchamia proces (także `mcp-proxy` z `stdio_client`) | **stdio przez Docker**, kroki 2–3 i 7 |

Obraz domyślnie uruchamia **HTTP**. Dla stdio trzeba jawnie podać `jev-decision-mcp --transport stdio` po nazwie obrazu. Nie podłączaj procesu HTTP do klienta stdio. Samo `McpError: Connection closed` oznacza zamknięcie połączenia podczas inicjalizacji; przyczyna znajduje się zwykle wcześniej w stderr procesu. Instrukcja diagnostyki jest w kroku 8.

Poniższe polecenia wykonuj w Bash na maszynie z Dockerem (np. Ubuntu 24.04 LTS). Python aplikacji i zależności instalują się **wewnątrz obrazu**; na hoście nie potrzebujesz uv ani środowiska `.venv`. Skrypt instalacyjny wymaga hostowego `python3`.

### 2. Przygotuj Docker

Jeżeli poniższe polecenia działają, przejdź do kroku 3:

```bash
docker version
docker compose version
```

`docker version` musi pokazać także sekcję Server. Na czystym Ubuntu zainstaluj Docker Engine i plugin Compose według [oficjalnej instrukcji Docker](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3 nano
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

Na maszynie z istniejącą instalacją Docker pomiń instalowanie pakietów. Dalsze polecenia zakładają dostęp do demona Docker bez sudo. Jeśli go nie masz, możesz dodać zaufane konto do grupy `docker` (daje uprawnienia zbliżone do root):

```bash
sudo usermod -aG docker "$USER"
```

Wyloguj się i zaloguj ponownie, a następnie sprawdź `docker version`. Host MCP uruchamiający stdio również musi mieć dostęp do Dockera; interaktywne pytanie o hasło sudo nie zadziała w jego `command`.

### 3. Pobierz projekt i ustaw klucz

```bash
mkdir -p "$HOME/services"
git clone https://github.com/ProgresjaIT/jev-decision-mcp.git "$HOME/services/jev-decision-mcp"
cd "$HOME/services/jev-decision-mcp"
chmod +x install.sh start.sh stop.sh healthcheck.sh update.sh
./install.sh
nano .env
```

Jeśli masz już projekt z Git lub ZIP, przejdź do jego katalogu i zacznij od `chmod`, bez ponownego klonowania. Prywatne repozytorium wymaga dostępu do konta GitHub.

W `.env` uzupełnij **tylko** `TYPESAFE_API_KEY` kluczem swojego konta TypeSafe. Zachowaj pozostałe wartości utworzone przez instalator:

```dotenv
TYPESAFE_API_KEY=TU_WSTAW_KLUCZ_TYPESAFE
MCP_TOKEN=TU_BEDZIE_TOKEN_WYGENEROWANY_PRZEZ_INSTALL_SH
HOST=0.0.0.0
DB_PATH=/data/history.sqlite3
COMPOSE_PROJECT_NAME=jev-decision
```

To ilustracja zawartości, **nie szablon do nadpisania pliku**. Instalator generuje losowy `MCP_TOKEN` i ustawia prawa `.env` na 600; ponowne uruchomienie zachowuje istniejący klucz i niepusty token. `TYPESAFE_API_KEY` służy do API TypeSafe, a `MCP_TOKEN` do połączenia klienta z serwerem HTTP. Nie są zamienne.

`HOST=0.0.0.0` jest adresem nasłuchu **wewnątrz kontenera**; Compose publikuje port hosta wyłącznie na `127.0.0.1`. `DB_PATH` wskazuje trwały wolumen. Instalator zachowuje własne ustawienia, więc w istniejącym `.env` sprawdź te dwie wartości.

### 4. Uruchom serwer HTTP

Z katalogu projektu:

```bash
docker compose config --quiet
./start.sh
docker compose ps
./healthcheck.sh
```

`start.sh` buduje obraz, sprawdza konfigurację, uruchamia usługę i czeka na healthcheck. Oczekiwany stan w `docker compose ps`: `Up` i `healthy`. Probe wykonuje prawdziwe MCP `initialize`, `list_tools` i lokalny `health_check`; wynik powinien zawierać `"tools": 10` oraz `"status": "approved"` w obiekcie `health`.

Ten test sprawdza obecność klucza i bazę, ale **nie jego ważność w TypeSafe**. Aby sprawdzić dostęp do API i modelu, wykonaj osobno test syntetyczny, który może naliczyć koszt:

```bash
./healthcheck.sh --api
```

Jeżeli uruchomienie się nie powiedzie:

```bash
docker compose logs --tail=200 jev
```

Nie publikuj `.env` ani wyniku `docker compose config` bez `--quiet`, bo mogą zawierać sekrety.

### 5. Podłącz klienta HTTP

Na tej samej maszynie adres to **`http://127.0.0.1:8765/mcp`**, transport **Streamable HTTP**. W hoście MCP wybierz połączenie przez URL, a w uwierzytelnianiu Bearer wpisz wartość `MCP_TOKEN` z `.env`. Przykład dla klienta obsługującego taki format JSON:

```json
{
  "mcpServers": {
    "jev-decision": {
      "url": "http://127.0.0.1:8765/mcp",
      "headers": {"Authorization": "Bearer WSTAW_MCP_TOKEN_Z_ENV"}
    }
  }
}
```

Zastąp placeholder rzeczywistym tokenem w prywatnej konfiguracji klienta. Sam klient nie odczyta automatycznie serwerowego `.env`. Test połączenia powinien wykryć 10 narzędzi; następnie wywołaj `health_check` z `{"check_api": false}`.

Sprawdzenie ochrony portu z hosta (bez tokenu):

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/mcp
```

Oczekiwany wynik: **401**. To test uwierzytelniania, nie pełnej komunikacji MCP. Wejście na URL w przeglądarce nie zastępuje testu MCP.

**Klient na innym komputerze:** możesz użyć tunelu SSH. Na komputerze klienta uruchom i pozostaw otwarty terminal:

```bash
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 UZYTKOWNIK@ADRES_SERWERA
```

Podmień dane SSH. Klient nadal używa `http://127.0.0.1:8765/mcp` i tego samego tokenu. Jeśli lokalny port jest zajęty, zmień pierwszy `8765` i port w URL klienta.

**Host MCP działa w kontenerze:** jego `127.0.0.1` oznacza ten kontener, nie host Docker ani kontener Jev. Użyj osiągalnego z niego adresu HTTPS przez reverse proxy. Konfiguracja domeny, TLS i `ALLOWED_HOSTS` jest w [INSTALL.md, punkt 7](INSTALL.md#7-https-firewall-uwierzytelnianie). Nie wystarczy zmienić URL na `host.docker.internal`, gdy usługa jest publikowana tylko na loopback hosta. Konfiguruj dostęp z rzeczywistego środowiska klienta.

### 6. Restart, zmiana ustawień i aktualizacja HTTP

Po zmianie `.env` odtwórz kontener — sam restart nie wczytuje nowych zmiennych:

```bash
docker compose up -d --force-recreate --wait --wait-timeout 90 jev
./healthcheck.sh
```

Zatrzymanie i ponowne uruchomienie:

```bash
./stop.sh
docker compose up -d --wait --wait-timeout 90 jev
```

Przy aktualizacji sprawdź lokalne zmiany, pobierz kod i uruchom skrypt aktualizacyjny:

```bash
git status --short
git pull --ff-only
./update.sh
```

Przed `git pull` zachowaj własne zmiany. `update.sh` tworzy kopię SQLite i zachowuje poprzedni obraz do rollbacku. Szczegóły aktualizacji z ZIP oraz przywracania: [INSTALL.md, punkt 10](INSTALL.md#10-aktualizacja-restart-stop-rollback).

Historia i liczniki pozostają w wolumenie `jev-decision-data` (lub nazwie z `JEV_DATA_VOLUME`). Nie usuwaj go ani nie używaj `docker compose down -v`, jeśli chcesz zachować dane. `restart: unless-stopped` wznawia usługę po restarcie Dockera, o ile wcześniej nie została ręcznie zatrzymana.

### 7. Docker przez stdio — dla hosta uruchamiającego command/args

Po krokach 2–3 zbuduj obraz; w tym wariancie nie uruchamiaj `start.sh` ani usługi HTTP:

```bash
docker build -t jev-decision-mcp:local .
docker run --rm --env-file "$PWD/.env" jev-decision-mcp:local jev-decision-mcp --check-config
```

Oczekiwany wynik drugiego polecenia: `Configuration valid`. Następnie ustaw w hoście MCP poniższą konfigurację, podmieniając **bezwzględną ścieżkę** do `.env`:

```json
{
  "mcpServers": {
    "jev-decision": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--env-file", "/home/TWOJ_UZYTKOWNIK/services/jev-decision-mcp/.env",
        "--mount", "type=volume,source=jev-decision-data,target=/data",
        "jev-decision-mcp:local",
        "jev-decision-mcp", "--transport", "stdio"
      ]
    }
  }
}
```

`-i` utrzymuje stdin dla protokołu MCP. **Nie dodawaj `-t` ani `-d`**: host potrzebuje bezpośrednich strumieni wejścia i wyjścia. Polecenie po nazwie obrazu zastępuje domyślny start HTTP. Nie używaj `docker compose up` jako komendy stdio.

`--env-file` jest obsługiwane przez Docker: przekazuje zmienne do procesu, mimo że sam serwer stdio nie czyta `.env`. Przy własnym `JEV_DATA_VOLUME` zmień też `source=` w argumentach — `docker run` nie interpretuje ustawień Compose. Wolumen zachowuje historię po zamknięciu kontenera przez host MCP.

Program `docker`, wskazany plik `.env` i dostęp do demona muszą istnieć **w środowisku uruchamiającym command**, także gdy jest nim proces `mcp-proxy`. Jeśli host działa w izolowanym kontenerze bez dostępu do Dockera, wybierz wariant HTTP zamiast tego wpisu. Obraz musi być zbudowany na demonie, z którym łączy się ten host.

Uruchom test połączenia w hoście: oczekiwane 10 narzędzi i `health_check({"check_api": false})` ze statusem `approved`. Ręcznie uruchomiony proces stdio może milczeć, czekając na komunikaty MCP — to normalne. `healthcheck.sh` służy wyłącznie do działającej usługi HTTP z Compose.

### 8. Diagnostyka `McpError: Connection closed`

Stos z `mcp_proxy` → `stdio_client` → `initialize()` pokazuje, że proxy próbuje rozmawiać z uruchomionym procesem przez stdio. Końcowy wyjątek nie ustala, dlaczego proces zakończył pracę. Sprawdź wcześniejsze logi stderr **w hoście MCP/proxy** i rzeczywiste `command`/`args`.

| Objaw lub wcześniejszy komunikat | Co sprawdzić |
|---|---|
| Host stdio uruchamia sam obraz lub `--transport http` | Zastosuj pełne `command`/`args` z kroku 7 albo przełącz klienta na HTTP z kroku 5. |
| `docker: not found`, `permission denied`, brak połączenia z daemonem | Sprawdź `docker version` jako użytkownik i w środowisku hosta MCP, nie tylko w swojej sesji SSH. |
| `env file not found`, `No such file or directory` | Podaj bezwzględną ścieżkę dostępną dla procesu uruchamiającego Docker. |
| `Unable to find image`, `pull access denied` | Zbuduj obraz na właściwym demonie i sprawdź zgodność tagu z `args`. |
| `Invalid configuration` | W HTTP sprawdź token (minimum 32 znaki), wartości liczbowe i `.env`; wykonaj walidację poniżej. |
| `ModuleNotFoundError` lub brak programu | Przebuduj obraz z katalogu zawierającego Dockerfile, `src` i pliki zależności. |
| SQLite `permission denied` / `readonly` | Użyj wolumenu montowanego w `/data`; proces w obrazie działa jako UID/GID 10001. |
| HTTP 401 | Klient musi wysyłać `MCP_TOKEN`, nie klucz TypeSafe. |
| HTTP 400 `Invalid host header` | Dodaj nazwę serwera do `ALLOWED_HOSTS` w `.env`, bez schematu/portu, i odtwórz kontener. |
| HTTP connection refused / timeout | Sprawdź `docker compose ps`, port i dostęp z sieci klienta; localhost w kontenerze to inna maszyna. |
| `healthy`, ale API nie działa | Lokalny healthcheck nie sprawdza dostawcy. Uruchom opcjonalne `./healthcheck.sh --api`. |

Diagnostyka wariantu HTTP z katalogu projektu:

```bash
docker compose ps -a
docker compose logs --tail=200 jev
docker compose run --rm --no-deps --entrypoint python jev -m jev_decision.server --check-config
```

W stdio brak klucza TypeSafe sam w sobie nie blokuje inicjalizacji ani listy narzędzi, ale uniemożliwia poprawne oceny. Jeśli błąd pozostaje, zbierz wcześniejszy stderr, komendę i argumenty bez sekretów, wersję obrazu oraz informację, czy host MCP działa na systemie czy w kontenerze.

Dalsze przykłady integracji: [examples/OPENHANDS.md](examples/OPENHANDS.md).

## Ograniczenia

Serwer ocenia wyłącznie przekazane dane. Nie pobiera samodzielnie informacji z CRM, Radar ani przeglądarki. Wynik modelu wymaga weryfikacji odpowiedniej do skutków działania. Porównanie Choice jest względnym wyborem między opcjami, nie niezależnym pomiarem jakości każdej z nich.

Wykonawca zmian musi osobno sprawdzać uprawnienia, aktualność danych i warunki zapisu. Przykład takiej kontroli: [docs/WRITE_GATE.md](docs/WRITE_GATE.md). Sam prompt nie wymusza używania walidacji przez agenta.

Limity kosztów obejmują tylko wywołania zapisane w tej bazie. Nie ograniczają rachunku całego konta TypeSafe. Usunięcie bazy usuwa historię i lokalne liczniki.

## Weryfikacja

```powershell
uv sync --extra test --python 3.12
uv run pytest -q
uv build
```

Testy sprawdzają oceny, progi, limity, obsługę błędów dostawcy, instalator oraz rzeczywistą komunikację MCP przez stdio i HTTP. Test stdio uruchamia osobny proces, inicjalizuje sesję, pobiera listę narzędzi i wywołuje lokalny `health_check`. Testy HTTP sprawdzają również token, nagłówek Host i odrzucanie żądań z Origin.

Domyślne testy nie wykonują płatnych zapytań i nie potwierdzają dostępu konta do modelu. Opcjonalny test rzeczywistego API, z kluczem już dostępnym w środowisku:

```powershell
$env:JEV_LIVE_TEST = "1"
uv run pytest tests/test_live.py -q -s
Remove-Item Env:JEV_LIVE_TEST
```

W wariancie Docker polecenie `./healthcheck.sh --api` również wykonuje płatny test syntetyczny. Zwykły `health_check` sprawdza tylko bazę i obecność klucza.
