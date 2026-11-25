# Obowiązkowa walidacja zapisów

`src/jev_decision/gate.py` zawiera działającą klasę `WriteGate`. Nie jest ona
narzędziem MCP wystawiającym dowolny URL, komendę lub nieograniczone uprawnienia.
Kod uruchamia się w **zaufanej usłudze wykonawczej**, której agent nie może edytować.
Agent przekazuje jedynie propozycję operacji. Polityka i tożsamość nie pochodzą
z tekstu agenta. Serwer Jev nie posiada kluczy Radar/CRM.

Bramka wykonuje: allowlistę operacji → ACL → sprawdzenie wersji → świeże pytanie
Noul i Choice ryzyka → wymaganie approved → ponowny ACL → callback atomowego zapisu.
Nie przyjmuje starego decision_id jako dowodu zatwierdzenia. Każda próba jest
oceniana na nowo. Testy sprawdzają blokady niepewności, błędów, CRM i braku ACL.

## Podłączenie do rzeczywistego wykonawcy

1. Nadaj OpenHands tylko odczyt Radar i CRM. Odbierz mu bezpośrednie klucze zapisu,
   dostęp do bazy, plików konfiguracyjnych i możliwość wywołania alternatywnych
   endpointów zapisu. Same filtry nazw narzędzi i prompt nie stanowią granicy.
2. Zbuduj osobny, uwierzytelniony endpoint proponowania zmian w zaufanym wykonawcy.
   Jego ACL mapuje tożsamość z uwierzytelnienia na dozwolone zasoby i operacje.
3. Zaufany wykonawca pobiera aktualną wersję i konieczne dane, minimalizuje je,
   odczytuje politykę administratora i wywołuje `WriteGate.execute`.
4. Callback `commit` wykonuje compare-and-swap: oczekiwana wersja jest sprawdzana
   i aktualizowana **w tej samej transakcji co zapis**. Brak CAS w Radar wymaga
   dodania go po stronie właściciela zapisu; lokalna blokada Pythona nie chroni
   przed innymi writerami. Konflikt wersji wymaga nowego stanu i nowej oceny.
5. Tylko ta usługa ma sekret zapisu Radar. CRM nie ma operacji zapisu na allowliście
   ani w uprawnieniach. Wysokiego ryzyka akcje wymagają niezależnej ścieżki człowieka.

`examples/guarded_writer.py` jest kompletnym lokalnym przykładem SQLite CAS,
przeznaczonym do adaptacji, nie gotowym adapterem nieznanego API Radar. Działa z
rzeczywistym Jev przez DecisionService. Prawdziwy wrapper HTTP/MCP i ACL domenowe
trzeba wpiąć w istniejący wykonawca na zdalnym serwerze po inspekcji jego API.
Nie twierdzimy, że obecne produkcyjne zapisy są już zabezpieczone tą bramką.

## Granice

Obowiązkowa walidacja działa tylko jeśli nie istnieje alternatywna ścieżka zapisu.
OpenHands z terminalem i produkcyjnymi kluczami może ominąć każdy prompt i hook.
Nie przekazuj takich kluczy do sandboxa. Shared MCP_TOKEN identyfikuje klienta
integracji, nie pojedynczego użytkownika; osobny ACL wykonawcy pozostaje konieczny.
Model ocenia dane probabilistycznie. Deterministyczne reguły bezpieczeństwa,
uprawnienia, walidacja schematu i limity zakresu działania obowiązują niezależnie.
