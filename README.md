# Jev Decision MCP

Uniwersalna warstwa ocen dla OpenHands i innych klientów MCP. Python 3.12,
oficjalny MCP SDK 2.3.0 (`MCPServer`, następca FastMCP), oficjalny
`typesafe-sdk` 0.7.5, Streamable HTTP `/mcp`, SQLite. Wersja 1.0.0.

**Instalacja na osobnym Ubuntu: [INSTALL.md](INSTALL.md).** Projekt nie wymaga WSL.

## Architektura

```text
OpenHands / automatyzacje ── HTTPS + Bearer ── reverse proxy
                                              │ loopback
                                      Jev Decision MCP
                                      │             │
                               TypeSafe SDK      SQLite volume
                                      │          metadane, budżet
                            api.typesafe.ai

Radar MCP / CRM MCP (read-only) → OpenHands → zminimalizowany kontekst → Jev
OpenHands → zaufany wykonawca → ACL → świeża walidacja Jev → atomowy zapis
```

Serwer niczego nie zmienia w Radar ani CRM. Wszystkie oceny są doradcze.
`approved` oznacza przejście progów określonej oceny, nie uprawnienie do zapisu.
Bramka wykonawcza jest oddzielnym modułem: [docs/WRITE_GATE.md](docs/WRITE_GATE.md).

## Narzędzia

| Narzędzie | Prymityw / znaczenie |
|---|---|
| `make_decision` | Choice, wybór jednej opcji |
| `evaluate_condition` | Noul, prawdopodobieństwo prawdziwości |
| `score_quality` | Score, 2–10 poziomów od najgorszego do najlepszego |
| `evaluate_risk` | Choice low/medium/high/critical; tylko low może przejść |
| `compare_options` | Choice, względne porównanie opcji |
| `classify_data` | Choice, jedna kategoria |
| `validate_action` | Noul zgodności + Choice ryzyka w jednym zapytaniu |
| `batch_decisions` | Jeden natywny request z mapą pytań i wspólnym kontekstem |
| `get_usage` | Trwałe lokalne statystyki, bez wywołania API |
| `health_check` | Lokalna kontrola; `check_api=true` wykonuje płatny test |

Wszystkie przykładowe argumenty: [examples/tools.json](examples/tools.json).
Klient uruchamiający przykłady: `python examples/call_tools.py` (patrz instalacja).

## Umowa odpowiedzi

Oceny zawierają `decision_id`, `status`, `meets_thresholds`, `results`,
`elapsed_ms`, `model`, `usage`, `estimated_cost_usd` i `cost_source`.
W `results` są oryginalne prawdopodobieństwa, confidence (jeśli istnieje),
wartość, status i poziom ryzyka dla pytania o ryzyko. Brakujące pola mają `null`.
Nie tworzymy uzasadnień tekstowych. Błędy wejścia wykryte na poziomie protokołu
MCP są standardowym błędem MCP, nie zatwierdzeniem.

- Noul: >= MIN_PROBABILITY zatwierdza stwierdzenie, <= NOUL_REJECT_THRESHOLD
  odrzuca, pozostałe wymagają przeglądu. `confidence=null`.
- Choice: wymagane MIN_CONFIDENCE i prawdopodobieństwo wybranej opcji >=
  MIN_PROBABILITY. Zwycięstwo opcji nazwanej „reject” nadal znaczy, że **wybór**
  jest wiarygodny, nie że działanie zostało zatwierdzone. Do zapisów używaj bramki.
- Score: skala 0..N-1. Wymagane MIN_CONFIDENCE i wynik/(N-1) >=
  SCORE_MIN_FRACTION. Niższa jakość przy odpowiedniej pewności = rejected.
- Ryzyko: pewne low = approved, medium = requires_review, high/critical =
  rejected; niepewna klasyfikacja zawsze requires_review.
- Batch/validate_action: rejected jeśli jakiekolwiek pytanie odrzucone,
  w przeciwnym razie requires_review jeśli choć jedno niepewne. Błędny format
  dowolnej odpowiedzi unieważnia cały batch. Błąd nigdy nie zatwierdza.

Progi są polityką operatora przez zmienne środowiskowe, nie parametrem agenta.
Domyślne progi są punktem startowym; skalibruj na oznaczonych przykładach Radar.
Porównanie opcji zwraca względny rozkład, nie niezależne oceny ani dowód poprawy.

## Koszty i prywatność

API dokumentuje tokeny wejściowe i wyjściowe, nie rachunek ani endpoint salda.
`get_usage` obejmuje wyłącznie tę bazę. Koszt jest estymacją przy stawkach z `.env`.
Rezerwacja obejmuje pełny standardowy limit 65536 tokenów wejściowych. Wyjście
jest obecnie bezpłatne. Bez automatycznych retry: timeout może już być płatny.
Nieznany koszt/błąd przed odczytem usage zachowuje rezerwację; restart jej nie usuwa.
Dzienny budżet UTC i licznik są wspólne dla procesów z tą samą bazą i atomowe.
Nie jest to limit rachunku konta TypeSafe: inne aplikacje, zmiany taryfy i modelu
są poza kontrolą tej usługi. Ustaw też limity dostawcy. Nie włączamy long context.

SQLite zapisuje UUID, dzień UTC, typ narzędzia, liczbę pytań, status, kod błędu,
czas i usage/koszt. Nie zapisuje kontekstu, odpowiedzi, opcji, promptów ani sekretów.
Brak automatycznej retencji: usuwanie historii zmienia statystyki i wymaga decyzji
operatora. Baza zawiera małe metadane, ale rośnie z liczbą wywołań.

Prosty filtr odrzuca rozpoznane sekrety i maskuje e-maile oraz telefony z prefiksem
międzynarodowym. Nie jest pełnym DLP. OpenHands musi używać allowlisty pól,
pseudonimizować klientów, usuwać nazwiska/adresy/sekrety także z instrukcji.
Stan zewnętrzny traktujemy jako dane; prompt injection nadal wymaga kontroli
wykonawcy. Domyślnie logi HTTP i treści SDK są wyłączone.

## Rozwój i testy

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest -q
# Jedno płatne syntetyczne zapytanie, jeśli klucz jest już w środowisku:
JEV_LIVE_TEST=1 .venv/bin/python -m pytest tests/test_live.py -q -s
```

[Testy i ograniczenia](docs/TEST_REPORT.md). Lokalnie nie wdrażano produkcji.

## OpenHands i Radar

[Konfiguracja i prompt](examples/OPENHANDS.md). Konfigurację MCP dodaj do każdego
profilu agenta / wspólnej fabryki `Agent`, z której korzystają automatyzacje.
Samo uruchomienie usługi nie rejestruje jej automatycznie we wszystkich profilach.
CRM musi mieć po stronie serwera wyłącznie uprawnienia odczytu.

## Oficjalne źródła sprawdzone 2026-11-25

- [TypeSafe System One API](https://docs.typesafe.ai/api/system-one)
- [Oficjalny SDK Python](https://docs.typesafe.ai/sdk/python)
- [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [Noul](https://docs.typesafe.ai/primitives/noul)
- [Modele, limity i ceny](https://docs.typesafe.ai/models), [błędy](https://docs.typesafe.ai/api/errors)
- [OpenHands MCP](https://docs.openhands.dev/openhands/usage/settings/mcp-settings)
- [OpenHands SDK](https://docs.openhands.dev/sdk/guides/mcp)
- [Migracja oficjalnego MCP SDK v2](https://py.sdk.modelcontextprotocol.io/v2/migration/)

API: `POST https://api.typesafe.ai/v1/systemone`, Bearer, `state`, `model`,
`questions`. Obsługujemy celowo tekstowe Choice/Score/Noul; eksperymentalne obrazy
oraz Box są poza zakresem. Brak zależności od nieoficjalnych hostów Jev.
