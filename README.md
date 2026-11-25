# Jev Decision MCP

Serwer MCP w Pythonie do ocen, klasyfikacji i wyboru działań przez TypeSafe Jev. Udostępnia 10 narzędzi opartych na Choice, Score i Noul z oficjalnego `typesafe-sdk`.

JEV ocenia przekazany kontekst i zwraca wynik wraz z prawdopodobieństwem oraz statusem. `validate_action` sprawdza zgodność działania i ryzyko w jednym zapytaniu. `batch_decisions` wykonuje kilka ocen ze wspólnym kontekstem w jednym zapytaniu.

Serwer przechowuje lokalną historię użycia w SQLite i pilnuje skonfigurowanych limitów kosztów oraz liczby wywołań. Oceny są doradcze. Serwer sam nie wykonuje ocenianych działań i nie zapisuje zmian w zewnętrznych aplikacjach.

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

## Osobny serwer HTTP / Docker

Wariant dla własnego serwera Ubuntu wymaga Docker Engine, Compose v2 i Python 3:

```bash
./install.sh
nano .env
./start.sh
./healthcheck.sh
```

Uzupełnij wyłącznie `TYPESAFE_API_KEY`. Instalator generuje `MCP_TOKEN` i ustawienia kontenera. Zachowuje istniejący klucz oraz token; uzupełnia brakujący lub pusty token. W tym wariancie konfiguracja jest przekazywana z `.env` do kontenera.

Docker uruchamia `jev-decision-mcp --transport http`. Endpoint to `http://127.0.0.1:8765/mcp`, z uwierzytelnianiem Bearer. Klient HTTP używa wygenerowanego `MCP_TOKEN`, a klucz TypeSafe pozostaje na serwerze. Port hosta jest publikowany tylko na loopback; zdalne połączenie wymaga skonfigurowania HTTPS lub prywatnego tunelu.

Pełna instalacja, reverse proxy, konfiguracja klienta HTTP, aktualizacja i rollback: [INSTALL.md](INSTALL.md). Integracja OpenHands: [examples/OPENHANDS.md](examples/OPENHANDS.md).

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
