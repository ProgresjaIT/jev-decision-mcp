# Podłączenie OpenHands

Docelowa instalacja OpenHands jest na osobnym serwerze, do którego ta sesja nie
miała dostępu. Nie znamy jej wersji ani istniejących MCP. Nie zastępuj obecnej
konfiguracji; dodaj jeden wpis po wykonaniu kopii. Adres musi być osiągalny
z runtime/sandbox OpenHands, nie tylko z przeglądarki administratora.

## Agent Canvas / aktualny interfejs

Customize → MCP Servers → Add custom server:

- Server name: `jev-decision`
- Server Type: `SHTTP`
- URL: `https://TWOJA-DOMENA/mcp`
- Authentication: `Bearer token`
- API Key: wartość `MCP_TOKEN` z serwera Jev (nie klucz TypeSafe)
- Timeout: 30 sekund przy TIMEOUT_SECONDS=20

Test connection powinien wykryć 10 narzędzi. Zapisz i rozpocznij nową rozmowę.
Zmiany nie dotyczą już uruchomionych rozmów. Dołącz MCP do profili wszystkich
potrzebnych automatyzacji. Nie edytuj ręcznie zaszyfrowanego settings.json.

## SDK: wspólna fabryka agentów

```python
import os
from openhands.sdk import Agent


def build_agent(llm, tools):
    return Agent(
        llm=llm,
        tools=tools,
        mcp_config={
            "mcpServers": {
                "jev-decision": {
                    "url": os.environ["JEV_MCP_URL"],
                    "headers": {
                        "Authorization": "Bearer " + os.environ["JEV_MCP_TOKEN"]
                    },
                }
            }
        },
    )
```

Wstaw wpis Jev do istniejącego `mcpServers`, zachowując pozostałe serwery.
Gotowy wzór JSON: [openhands-sdk.json](openhands-sdk.json). Zastąp placeholdery;
nie zakładaj interpolacji `${...}` przez OpenHands. Plik z prawdziwym tokenem ma
mieć chmod 600 i nie może trafić do repozytorium.

Starsze wydania aplikacji z `mcp_config.shttp_servers` mogą używać
[openhands-legacy.json](openhands-legacy.json). To alternatywny format, nie druga
równoczesna konfiguracja. Weryfikuj schemat na własnej wersji `/api/settings`;
nie wysyłaj przykładowego obiektu w ciemno jako zastępstwa wszystkich ustawień.

## Prompt do AGENTS.md / instrukcji automatyzacji

> Jesteś wykonawcą analizy Radar. Pobieraj tylko konieczne dane z Radar MCP i CRM
> MCP. CRM jest wyłącznie do odczytu. Usuń sekrety i dane identyfikujące klientów;
> używaj agregatów, pseudonimów i zanonimizowanych przykładów postów.
> Najpierw wywołaj evaluate_condition, aby ocenić potrzebę optymalizacji, oraz
> classify_data dla trafności postów. Użyj score_quality do promptów i filtrów,
> compare_options do porównania obecnego i proponowanego promptu. Uwzględniaj
> niezależne dane walidacyjne, liczbę przykładów i możliwość regresji.
> Przed propozycją zapisu użyj validate_action; evaluate_risk służy dodatkowej
> ocenie ryzyka. rejected, requires_review lub error zatrzymują automatyczny zapis.
> Nie próbuj ponownie aż do uzyskania korzystnej odpowiedzi. Przekaż wątpliwości
> operatorowi. Każdy zapis wykonuje wyłącznie zaufana bramka z niezależnym ACL,
> polityką, świeżą walidacją i kontrolą wersji. approved nie daje nowych uprawnień.
> Raportuj UUID decyzji, wyniki, niepewności i tokeny; nie wymyślaj uzasadnień Jev.

## Pierwsze zastosowanie: Radar

1. Odczyt: agregaty klienta, błędne dopasowania, próbka pozytywów/negatywów,
   wersja konfiguracji. Nie wysyłaj nazwiska ani całego rekordu CRM.
2. `evaluate_condition`: czy udokumentowana jakość wymaga optymalizacji?
3. `classify_data`: post pasujący / niepasujący / niejednoznaczny.
4. `score_quality`: prompt lub filtr, opisowe poziomy jakości.
5. `evaluate_condition`: czy zmiana ma wsparcie w danych i spełnia cel?
6. `compare_options`: obecny / proponowany / brak podstaw do wyboru.
7. `evaluate_risk`: ryzyko zmiany z planem rollbacku i zakresem oddziaływania.
8. `validate_action`: zgodność ze wszystkimi warunkami oraz niskie ryzyko.
9. Zaufany wykonawca ponownie pobiera aktualny stan, sam ustala politykę,
   sprawdza ACL i wykonuje świeżą ocenę przed atomowym zapisem.

W przykładach `tools.json` są syntetyczne dane. Rzeczywiste metryki i kryteria
należy dobrać do procesu. Jev nie zastępuje pomiaru poprawy na zbiorze testowym.
