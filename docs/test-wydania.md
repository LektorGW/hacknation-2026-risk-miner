# Test wydania Risk Miner 1.0

Wydanie sprawdzono 22 listopada 2026 r. na Windowsie z Docker Desktop i w kontenerze Linux. Aplikację uruchomiono w trybie produkcyjnym z uwierzytelnianiem na porcie 8180. Baza i pliki przetrwały odtworzenie kontenera.

## Wyniki

| Sprawdzenie | Wynik |
|---|---|
| Testy automatyczne z repozytorium | 58 testów i 4 podtesty zakończyły się powodzeniem. Klient testowy Starlette zgłasza ostrzeżenie o zmianie zależności. |
| Publiczne akta umowy | Sprawdzono wybór daty i trzy inwestycje w przeglądarce przy szerokościach 390 i 1440 px. Widok pokazuje tylko dokumenty opublikowane do wybranego dnia. |
| Pulpit i porównanie źródeł | Na szerokościach 1440 i 390 px sprawdzono logowanie, pulpit i przejście do rozbieżności. W obu ogłoszeniach z Zagrodna otwarto pole 4.2 z oryginalnym okresem umowy. Test pominięcia Biecza dał 396–442 dni, a wybrany wariant zapisano w Wordzie i JSON. |
| Integralność wejścia | Arkusz dał 22 projekty. Załączniki rozpoznano jako 26 akapitów DOCX, stronę tekstowego PDF i stronę skanu odczytaną OCR. |
| Walidacja odnośników | Wszystkie 76 plików BZP z migawki pobrano i porównano numer ogłoszenia na pierwszej stronie. Dodatkowy wpis pochodzi z rejestru KPO. [Szczegóły prób i ograniczeń](walidacja-zrodel.md) |
| Powtórne wzbogacenie Zagrodna | Na izolowanej bazie odtworzono pięć archiwalnych obserwacji. Pierwszy pełny odczyt znalazł sześć źródeł i dodał jedną korektę, drugi dodał zero. Zachowano identyfikatory, umowę i kolejkę decyzji. Sprawdzono klucze obce. |
| Decyzja eksperta | Zmiana przypisania pomiaru przeniosła go między umowami. Oryginalny tekst zachował tę samą treść. Nieaktualna wersja decyzji otrzymała HTTP 409. |
| Próba historyczna | Ukryto późniejsze źródła i wyłączono badany projekt z grupy. Test zmienia katalog po zapisaniu wskazań i potwierdza, że odsłonięcie pod tym samym identyfikatorem zachowuje wcześniejsze wyniki. |
| Typowa analiza nowego projektu | Przykładowy plan umowy na 365 dni miał 14 podobnych projektów i 7 umów z porównywalnymi pomiarami czasu. Historyczne odchylenia w tej grupie wyniosły od 0 do 77 dni. Roboczy scenariusz dla tego planu wyniósł 365–442 dni. Włączono podgląd powiązań po identyfikatorach. |
| Przenoszenie wyniku do akt | Z zapisanej analizy pobrano DOCX, otwarto dokument, sprawdzono jego skład i eksport do PDF. W przykładzie zachowano status roboczy oraz oznaczenie wykorzystania źródeł oczekujących na weryfikację. |
| Interfejs | W Chromium sprawdzono import, źródło, korektę, zapis analizy, Word, odsłonięcie próby, nową kategorię i zmianę sektora. Dziesięć widoków sprawdzono na ekranie 390 × 844. Logowanie i pobranie chronionego źródła sprawdzono również na instancji 8180. |
| Nowy sektor | Dodano konfigurację transportową przez interfejs, przypisano jej regułę i odtworzono analizę. Zmiana na wod-kan usunęła z porównania przypadek i regułę transportową. |
| Dostęp i odtworzenie | Zweryfikowano role, odmowę operacji z obcej domeny oraz odczyt źródła przez uprawnione konto. Osobną kopię otwarto jako bazę API, pobrano załącznik o zgodnym SHA-256 i odtworzono rozbieżność z Zagrodna. |
| Krótka próba równoległa | 12 odczytów pulpitu przy 4 równoczesnych klientach na tym komputerze. Mediana 263 ms, najdłuższy odczyt 357 ms. Pomiar obejmował lokalny HTTP i odczyt JSON. |
| Pakiety | `pip check` potwierdził spójność zależności kontenera. `pip-audit` dla wersji z constraints.txt nie zgłosił znanych podatności w chwili sprawdzenia. |

Pomiar 12 odczytów opisuje obciążenie na stanowisku pilotażowym. Nie ustalano na jego podstawie maksymalnej liczby użytkowników ani SLA. Skuteczność prognoz wymaga osobnej walidacji na większym, niezależnym zbiorze. W trybie domyślnym przetwarzanie jest lokalne, a próby opcjonalnego klienta modelu obejmują jego zachowanie protokolarne.

## Audyt wydania konkursowego

| Obszar | Wynik sprawdzenia po poprawkach |
|---|---|
| Części zamówienia i koszty | Brak pola dla wskazanej części pozostawia pomiar pusty. Tekst o niejednoznacznej podstawie netto/brutto nie trafia do porównania kwot. Na 22 projektach organizatora zachowano wyniki kosztu i czasu dla 21 porównywalnych umów. |
| Import i wzbogacanie | CSV zgłasza nadmiarowe komórki. BZP i TED zachowują poprawne rekordy przy awarii dalszej strony. Po zaimportowaniu 22 projektów do pustej bazy dwa pobrania Zagrodna dały po pięć ogłoszeń BZP i jeden wpis KPO. Pierwsze dodało jedną obserwację, drugie zero. |
| Historia i decyzje | Powtórzenie identycznej analizy przywraca zapisaną ocenę. Przy równoległej decyzji interfejs pokazuje aktualną ocenę i komentarz drugiego eksperta. Osobne testy obejmują wykluczenie projektu po jego identyfikatorze CST i pomijanie późniejszych korekt przy próbie historycznej. |
| Publiczne akta i dostępność | W Chrome sprawdzono siedem etapów trzech inwestycji przez HTTP i z dysku przy wyłączonym JavaScripcie. Każda karta dowodowa zawierała źródła dostępne w wybranym dniu. Osiem widoków aplikacji sprawdzono przy szerokościach 390 i 1440 px. W menu mobilnym sprawdzono Tab, Shift+Tab oraz Escape. |
| Raport | Karta Word zachowuje decyzję eksperta i odpowiedź z aneksu. Otworzono dokument z tekstem OCR i wyrenderowano przykładową kartę w LibreOffice. Przez interfejs pobrano również Word i JSON z tym samym wybranym wariantem harmonogramu. |

Odczyty z czytnikiem ekranu i testy w Safari pozostają do wykonania. Wyniki próby prognostycznej na ośmiu postępowaniach opisuje [odrębny raport](test-niezalezny.md).

## Materiały

[Eksport analizy nowej inwestycji (JSON)](../deliverables/przyklad-analizy.json) zawiera opis planowanej kanalizacji z przepompownią, przyjęty budżet 5 mln zł i harmonogram 365 dni. W wyniku można sprawdzić dobór projektów porównawczych, podstawę pomiarów i pytania do dokumentacji. Włączony podgląd obejmuje także powiązania oczekujące na ocenę eksperta.

[Test łączenia rekordów i oryginalne ogłoszenia](walidacja-zrodel.md) · [Trafność ostrzeżeń na ośmiu nowych postępowaniach](test-niezalezny.md)

W wersji z testem wrażliwości dodatkowo sprawdzono warianty po pominięciu każdej inwestycji, remisy na granicach przedziału i ograniczenie do minimum trzech pomiarów. Test przeglądarkowy objął przełączenie z terminu na koszt, wybór projektu, odczyt źródeł oraz zgodność identyfikatora w eksportach Word i JSON. Na szerokości 390 pikseli widok mieścił się bez poziomego przewijania. W odrębnym projekcie Docker sprawdzono przekierowanie HTTP, TLS 1.3 z zaufanym w teście lokalnym urzędem certyfikacji, odpowiedź zdrowia i odmowę dostępu do danych bez tokenu. Wydanie certyfikatu dla publicznej domeny wymaga skonfigurowanego serwera instytucji.

- [Film z przebiegu pracy](../deliverables/demo-risk-miner.mp4)
- [Prezentacja dla jury](../deliverables/prezentacja-risk-miner.pdf)
