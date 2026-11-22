# Test wydania Risk Miner 1.0

Wydanie sprawdzono 22 listopada 2026 r. na Windowsie z Docker Desktop i w kontenerze Linux. Aplikację uruchomiono w trybie produkcyjnym z uwierzytelnianiem na porcie 8180. Baza i pliki przetrwały odtworzenie kontenera.

## Wyniki

| Sprawdzenie | Wynik |
|---|---|
| Testy automatyczne z repozytorium | 39 testów i 4 podtesty zakończyły się powodzeniem. Biblioteka klienta testowego informuje o przyszłej zmianie zależności. |
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

## Materiały

W wersji z testem wrażliwości dodatkowo sprawdzono warianty po pominięciu każdej inwestycji, remisy na granicach przedziału i ograniczenie do minimum trzech pomiarów. Test przeglądarkowy objął przełączenie z terminu na koszt, wybór projektu, odczyt źródeł oraz zgodność identyfikatora w eksportach Word i JSON. Na szerokości 390 pikseli widok mieścił się bez poziomego przewijania. W odrębnym projekcie Docker sprawdzono przekierowanie HTTP, TLS 1.3 z zaufanym w teście lokalnym urzędem certyfikacji, odpowiedź zdrowia i odmowę dostępu do danych bez tokenu. Wydanie certyfikatu dla publicznej domeny wymaga skonfigurowanego serwera instytucji.

- [Film z przebiegu pracy](../deliverables/demo-risk-miner.mp4)
- [Prezentacja dla jury](../deliverables/prezentacja-risk-miner.pdf)
- [Przykład edytowalnej karty](../deliverables/karta-inwestycji.docx)
- [Dane wejściowe i wynik tej analizy](../deliverables/przyklad-analizy.json)
