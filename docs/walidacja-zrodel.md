# Walidacja źródeł i powiązań

Odczyty wykonano 22 listopada 2026 r. W arkuszu organizatora znajdowały się 22 przedsięwzięcia. Dla każdego odnaleziono co najmniej jeden publiczny dokument. Migawka w aplikacji obejmuje 76 ogłoszeń BZP i jeden wiersz regionalnego wykazu KPO. Jedna umowa może mieć kilka ogłoszeń o wykonaniu. Liczebność grupy porównawczej wymaga liczenia odrębnych kontraktów z zatwierdzonymi pomiarami. [Pochodzenie danych i odtworzenie migawki](../fixtures/real/README.md)

## Odczyty na żywo

| Próba | Zaobserwowany wynik |
|---|---|
| Zagrodno, RM-2026-002, dwa odczyty | W obu odczytach te same 5 numerów BZP i 1 wpis KPO. BZP zwrócił ogłoszenie o zamówieniu, korektę ogłoszenia, wynik oraz dwa ogłoszenia o wykonaniu. Bieżąca korekta `2026/BZP 00108931/01` jest dodatkowym wynikiem wobec migawki konkursowej. TED zwrócił pusty wynik dopasowania. Drugi odczyt trwał 10,44 s. |
| Gościeradów, RM-2026-006, z numerem BZP | 5 ogłoszeń przypisanych do jednego OCID na podstawie numeru z arkusza. Wynik, dwie zmiany i wykonanie umowy uzupełniły ogłoszenie początkowe. Odczyt trwał 11,41 s. |
| Gościeradów, ten sam rekord, usunięty numer BZP | W odpowiedzi pojawiły się odrębne postępowania o takim samym tytule. System zgłosił konieczność porównania OCID. Jedno z dalszych zapytań do urzędu nie powiodło się. Zachował sześć pobranych kandydatur i komunikat o częściowym wyniku. |
| Zakrzew, RM-2026-009 | W jednym przebiegu zwrócono tylko bazowe ogłoszenie, a kolejne zapytanie BZP zakończyło się błędem. Zachowano numer i zgłoszono przerwany odczyt. Ponowienie po ustąpieniu błędu zwróciło 5 ogłoszeń BZP w 11,91 s, w tym wynik z umową części 2 i wykonanie `2025/BZP 00568661/01`. TED poprawnie zwrócił zero dopasowań. |
| TED, dodatnia kontrola na odrębnym zamówieniu | Wysłano żądanie POST z numerem publikacji do Search API v3. Odpowiedź dla `3577-2024` zawierała Miasto Katowice, tytuł usługi odprowadzania wód opadowych i procedurę `a96757be-5cfb-4e76-b190-e883e6ce176f`. Ten test sprawdza integrację TED poza krajową próbą organizatora. [Ogłoszenie TED](https://ted.europa.eu/pl/notice/3577-2024/pdf) |

Serwisy mogą zwracać ograniczenia ruchu i wyniki częściowe. BZP publikuje limit 30 odczytów na minutę z jednego IP. Pojedynczy proces aplikacji odstępuje co najmniej 2,1 s między początkami kolejnych zapytań do publicznego endpointu wyszukiwania BZP. Osobno raportowane są stan źródła i liczba dopasowań. Udany odczyt z zerem pasujących ogłoszeń jest poprawnym wynikiem wyszukiwania. [Instrukcja BZP i limit](https://ezamowienia.gov.pl/pl/integracja/) · [Dokumentacja API TED](https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html)

## Kontrola niezależna od wyniku podobieństwa

Sprawdzono osobno wszystkie 76 odsyłaczy BZP z migawki. Każdy adres z urzędowym identyfikatorem UUID zwrócił plik PDF. Na pierwszej stronie każdego pliku odnaleziono spodziewany numer ogłoszenia. Kontrola obejmowała wszystkie 22 projekty, także przypadki z wieloma częściami i kolejnymi ogłoszeniami o wykonaniu. Wszystkie 76 z 76 odsyłaczy przeszło ten test 22 listopada 2026 r. Oddzielnie pobrano urzędowy czterostronicowy PDF KPO i pięciostronicowy PDF dodatniej kontroli TED.

Punktem odniesienia były numery i zakresy z arkusza oraz treść oryginalnych PDF pobranych z urzędu, oddzielnie od generatora przypadków. Sprawdzano numer w nagłówku, sekcję o poprzednim ogłoszeniu, część zamówienia, datę podpisania i kwotę umowy, zależnie od badanego powiązania. Wydzielono pięć dodatnich par i dwie kontrolne pary błędne. Wszystkie pięć dodatnich znalazło się w zestawie. Obie błędne pozostały poza zestawem. Dodatkowa próba z usuniętym identyfikatorem miała niejednoznaczny wynik.

| Rodzaj | Para | Sprawdzenie |
|---|---|---|
| Dodatnia | Oława → wykonanie `2026/BZP 00147223/01` | Sekcja III.3.2.1 wskazuje numer z arkusza `2022/BZP 00058537/01`. Umowa opiewała na 2 107 348,39 zł, a wypłacono 2 246 177,66 zł. [PDF urzędu](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08de7e88-bd39-dafb-056e-e50001ac5cf9) |
| Dodatnia | Biecz, część 1 → wykonanie `2026/BZP 00255110/01` | Wskazane w dokumencie numer postępowania i część 1 zgadzają się z arkuszem. [PDF urzędu](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08deb72a-3c2d-0f0d-5fad-9500012ba59e) |
| Dodatnia | Zakrzew, część 2 → wykonanie `2025/BZP 00568661/01` | Ogłoszenie powołuje numer wyniku. Z sekcją VIII dla części 2 zgadzają się 25 sierpnia 2025 r. i 1 810 533,92 zł. [Wynik](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08ddf422-20e0-3e31-d903-3900014ec36f) · [Wykonanie](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08de317b-5a9a-356c-0560-490001c57d08) |
| Dodatnia | Wolin → wykonanie części 2 `2024/BZP 00621519/01` | Sekcja III.3.2.1 zawiera numer z arkusza `2023/BZP 00110672`. W tym przypadku sam dokument o wykonaniu zachowuje dowód odwołania do wcześniejszego ogłoszenia. [PDF urzędu](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08dd0f9a-2990-af9e-985c-bb0001355be0) |
| Dodatnia | Zagrodno → wykaz KPO | Na stronie 2 wiersz 25 wskazuje `KPOD.03.15-IW.13-0004/25`, gminę i nazwę inwestycji. Kwota 4 770 558,05 zł jest wartością wnioskowanego wsparcia. [Wykaz UMWD](https://umwd.dolnyslask.pl/fileadmin/user_upload/KPO/2025.12.18_Zalacznik_do_Uchwaly_zaktualizowana_lista_przedsiewziec.pdf#page=2) |
| Błędna para kontrolna | Biecz, część 1 → wykonanie części 2 `2026/BZP 00255135/01` | Weryfikacja zakresu eliminuje dokument mimo wspólnego OCID. PDF wprost wskazuje część 2. [PDF urzędu](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08deb72a-eec5-1121-5fad-9500012ba5be) |
| Błędna para kontrolna | Gościeradów, postępowanie wskazane numerem z 2024 r. → unieważnienie w 2023 r. | Dwa postępowania mają ten sam tytuł i zamawiającego oraz różne OCID. Wynik z 2024 r. przywołuje numer z arkusza w sekcji II.2.14. Błędna para została odfiltrowana. [Wynik z 2023 r.](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08db6e4d-5733-f2b9-d0a9-9e0012b90dc0) · [Wynik z 2024 r.](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08dc442f-05d5-6d14-5566-8b00013bf2ce) |
| Niejednoznaczna | Gościeradów, dopasowanie po nazwie i zamawiającym po usunięciu numeru | Pojawiają się m.in. procedury `ocds-148610-47b13815-0064-11ee-b70f-ae2d9e28ec7b` i `ocds-148610-89142c9f-bb81-11ee-b7da-22bd761ba7f3`. Można skontrolować oba wyniki i podjąć decyzję ekspercką. |

W Zagrodnie dwa ogłoszenia wskazują tę samą podpisaną umowę i kwotę, ale podają okres realizacji 3 oraz 2 miesiące. Oba dokumenty są widoczne w historii. Klucz kontraktu jest wspólny. Rozbieżność jest przesłanką do oceny eksperta. [Wcześniejsze ogłoszenie](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08dec528-4925-88ea-5fad-9500015c65f4) · [Późniejsze ogłoszenie](https://ezamowienia.gov.pl/mo-board/api/v1/Board/GetNoticePdfById?noticeId=08dec7a5-add3-9ae4-5fad-950001d1b535)

To próba celowa z przypadkami wieloczęściowymi i powtórzonym postępowaniem. Zamknięty zbiór referencyjny jury pozostaje niedostępny. Wynik opisuje wymienione pary. Oszacowanie precyzji i czułości dla całego rejestru wymagałoby niezależnie oznaczonej próby obejmującej również przeoczone dokumenty.

## Import plików uczestnika

| Plik | Wynik rzeczywistego importu |
|---|---|
| XLSX z rekordami | 22 projekty, 22 odsyłacze do wierszy i zachowane identyfikatory. Zakładka z definicjami kolumn pominięta. |
| Protokół Zławieś Wielka, DOCX | 26 fragmentów z numerami akapitów. Pierwszy akapit zawiera miejscowość i datę 28.10.2025 r. |
| Protokół Zagrodno, PDF | 1 strona odczytana z natywnej warstwy tekstowej. W treści rozpoznano numer `KPOD.03.15-IW.13-0004/25`. |
| Pismo Grodzisko Dolne, PDF | 1 strona odczytana przez lokalny OCR w Windows. Lokalizator ma oznaczenie „strona 1 (OCR)”. Użycie wbudowanego OCR zajęło w tym przebiegu ok. 2,6 s. |

Dodatkowo sprawdzono rzeczywisty binarny plik testowy XLS zapisany przez xlwt. Po imporcie zachowano początkowe zero w tekstowym NIP. Wszystkie 12 testów źródeł i importu zakończyło się poprawnie. Objęły m.in. znaki polskie, zduplikowane nagłówki, źródła akapitów i tabel DOCX, uszkodzone pliki, pusty PDF, zakres części, kursor paginacji, formaty numeru TED i odseparowanie błędu jednego serwisu. Polecenie uruchamia testy z katalogu głównego.

```sh
python -m unittest discover -s tests -p test_sources.py -v
```
