# Wyniki weryfikacji

Data: 2026-11-25. Środowisko: lokalny Linux/WSL, Python 3.12.14.
Nie wykonywano wdrożenia produkcyjnego.

## Testy automatyczne

`python -m pytest -q`: **49 passed, 1 skipped** (2.18 s).
Pominięty test to domyślnie wyłączony płatny test inferencji TypeSafe.

Zakres:
- wszystkie 10 narzędzi przez rzeczywisty klient MCP i tymczasowy serwer HTTP;
- initialize, tools/list, tools/call, structuredContent;
- Choice, Score, Noul, mieszany batch w jednym wywołaniu;
- prawdziwy SDK TypeSafe z kontrolowanym transportem HTTP: serializacja,
  odpowiedzi, 401, 429, 500, 529, brak automatycznych retry;
- progi prawdopodobieństw, confidence i jakości, wszystkie klasy ryzyka;
- timeout oraz wymuszony deadline, brak klucza, błędne struktury odpowiedzi;
- limity rozmiaru i batch, limit kosztu pojedynczego requestu i liczby wywołań;
- atomowe rezerwacje budżetu przy współbieżności oraz po restarcie obiektu usługi;
- trwałość usage, brak pełnego kontekstu w SQLite, blokada sekretów, maskowanie PII;
- błędny Bearer, Origin, Host; brak wycieku sekretów w błędach startu;
- odmowa zapisu przy error/requires_review/rejected, niezależne ACL, blokada CRM;
- przykład atomowego zapisu CAS odrzucający powtórzenie wersji;
- idempotencja install.sh i prawa 600 nowego `.env`.

Ruff check i format --check: PASS (20 plików Pythona).
`bash -n` pięciu skryptów: PASS.
Compose config --quiet z przykładowym plikiem środowiska: PASS.
Docker build końcowego kodu: PASS.
Test tymczasowego kontenera bez roota, z read-only filesystem, bez sieci
zewnętrznej i bez publikowanych portów: PASS. Rzeczywisty klient MCP wykrył
10 narzędzi i wykonał health_check (API nie było wywoływane). Kontener usunięty.

## Rzeczywisty TypeSafe

Wykonano test z istniejącym lokalnym kluczem, bez kopiowania go do projektu.
Stan był syntetyczny: kolor blue i jakość excellent; jeden batch Choice/Score/Noul.
Pierwsze podejście w sandboxie zakończyło się timeoutem. Po uzyskaniu dostępu
sieciowego oficjalne API zwróciło **TypeSafeAuthenticationError**. Test inferencji
zakończył się niepowodzeniem. Nie uzyskano prawidłowej odpowiedzi modelu ani usage.
Nie przedstawiamy mocków jako potwierdzenia poprawnej inferencji produkcyjnej.
Należy uzupełnić ważny TYPESAFE_API_KEY i uruchomić `./healthcheck.sh --api` oraz
opcjonalny `JEV_LIVE_TEST=1 python -m pytest tests/test_live.py -q -s`.

## OpenHands i infrastruktura

Lokalne `docker ps` nie wykazało działających kontenerów. Nie znaleziono lokalnego
katalogu ustawień OpenHands. Zdalnego serwera, wersji OpenHands, profili agentów,
portów, sieci ani konfiguracji MCP nie udostępniono tej sesji. Nie wykonano zmian
w Radar, CRM ani istniejących MCP. Nie ma stale działającego endpointu z tej sesji.

Formaty konfiguracji przygotowano na podstawie aktualnej oficjalnej dokumentacji.
Po stronie zdalnego OpenHands wymagane pozostają: Test connection, nowa rozmowa,
health_check, get_usage oraz powtórzenie w runtime każdej automatyzacji.
Adapter zapisu do rzeczywistego Radar i jego ACL/CAS wymaga podłączenia w zaufanym
wykonawcy. Dostarczony moduł i przykład SQLite są przetestowane, lecz nie zmieniają
zabezpieczeń istniejącego serwera Radar.

Instalacja Dockera/HTTPS na czystym zdalnym Ubuntu i produkcyjny rollback nie były
wykonywane. Instrukcja zawiera pełne kroki; skrypty nie nadpisują `.env` i nie usuwają
wolumenów. Testy transportu oraz kontenera są lokalnymi testami integracyjnymi.
