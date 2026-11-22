# Przypadki referencyjne Risk Minera

`cases.json` zawiera 22 publiczne przedsięwzięcia z arkusza MFiPR i 77 powiązanych dokumentów źródłowych. Każdy przypadek ma oryginalne pola arkusza, ich znormalizowaną postać, numer wiersza i propozycje powiązań. `projects.csv` służy do samodzielnego sprawdzenia importu i zapytań do rejestrów. W aplikacji decyzja eksperta jest osobnym rekordem.

| Źródło | Co zawiera próbka | Pochodzenie |
|---|---|---|
| MFiPR / HackNation 2026 | 22 wiersze, 15 numerów BZP, 7 identyfikatorów KPO. Biecz obejmuje część 1, Zakrzew część 2. | [Arkusz organizatora](../starter/Risk_Miner_dane_projekty.xlsx), zakładka „Projekty”, wiersze 2–23. SHA-256 pliku `b10b57a14d6f188004f38bb73a99ee1e3226c43166a6e8edd500ea5fda21eabe`. |
| Urząd Zamówień Publicznych, BZP | 21 ogłoszeń o zamówieniu, 21 o wyniku, 24 o wykonaniu i 10 o zmianie umowy | [Oficjalny odczyt BZP](https://ezamowienia.gov.pl/pl/integracja/) i [kopia udostępniona uczestnikom](https://bzp.cytr.us/paczka/risk_miner_bzp_kopia.zip). Manifest kopii podaje datę 12 listopada 2026 r. i 113 278 ogłoszeń. |
| Urząd Marszałkowski Województwa Dolnośląskiego | Wiersz z wnioskowaną kwotą wsparcia dla Zagrodna, przypisany do numeru KPO. | [Lista przedsięwzięć B3.1.1 z 18 grudnia 2025 r., strona 2, pozycja 25](https://umwd.dolnyslask.pl/fileadmin/user_upload/KPO/2025.12.18_Zalacznik_do_Uchwaly_zaktualizowana_lista_przedsiewziec.pdf#page=2). |

Podczas odczytu BZP aplikacja zapisuje identyfikator ogłoszenia, OCID, typ, datę publikacji, datę odczytu, adres pobrania, link do urzędowego PDF i podstawę powiązania. Pole `sha256` jest skrótem tekstu wyodrębnionego z całego urzędowego HTML. Pole `excerpt_sha256` obejmuje faktycznie zapisaną treść po pominięciu sekcji adresowych i danych kontaktowych. Etykiety i numeracja pól pozostają w tekście. Wartość `confidence` jest wynikiem reguł podobieństwa w skali 0–1. Zachowano także dwa sprzeczne raporty dla tego samego kontraktu w Zagrodnie.

## Odtworzenie danych

W katalogu głównym repozytorium, po zainstalowaniu zależności Pythona, polecenia pobierają kopię organizatora i tworzą nową wersję zestawu w osobnym katalogu.

```sh
curl -fL --retry 2 https://bzp.cytr.us/paczka/risk_miner_bzp_kopia.zip -o risk_miner_bzp_kopia.zip
python -m riskminer.benchmark fixtures/starter/Risk_Miner_dane_projekty.xlsx risk_miner_bzp_kopia.zip odtworzony-zestaw
```

Generator sprawdza sumę kontrolną strumienia `notices.jsonl.xz` względem manifestu. Dla zweryfikowanej kopii SHA-256 wynosi `af0e37f5bbc6ee72c7431e3d6ef4572b550a95c4667a5abd3d868ac3dbfa8654`. Następnie wyszukuje ogłoszenia według numeru i sprawdza zamawiającego, tytuł, część oraz OCID. Gdy brakuje ogłoszenia początkowego, może ustalić jego numer z odwołania w ogłoszeniu o wykonaniu. Dla rekordów KPO wymaga zgodności tytułu i zamawiającego przy wyszukiwaniu postępowania. Dołącza pasujące po numerze wpisy z regionalnego rejestru KPO. Ponowne odtworzenie aktualizuje datę odczytu.

W trybie online aplikacja korzysta domyślnie z bieżącego BZP i TED. Zmienna `RISKMINER_BZP_MIRROR=1` przełącza odczyt BZP na kopię HackNation. Ta kopia obejmuje sektor wodno-kanalizacyjny i cztery typy ogłoszeń. Nie zawiera m.in. osobnych korekt ogłoszenia. Źródło i datę danych można sprawdzić przy każdym wyniku. TED jest integrowany przez [publiczne Search API](https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html).

## Warunki źródeł

Organizator udostępnił arkusz i kopię ogłoszeń do realizacji wyzwania. Manifest opisuje zawartość jako publiczne dane BZP. Podczas dalszego wykorzystania trzeba zachować atrybucję źródła, datę i oryginalny odsyłacz. Odczyt z BZP podlega regulaminowi platformy i opublikowanym limitom. [Regulamin e-Zamówień](https://ezamowienia.gov.pl/pl/regulamin/) · [Instrukcja i limit API BZP](https://ezamowienia.gov.pl/pl/integracja/)

UMWD jest wydawcą przytoczonego wykazu. Próbka zawiera jeden wiersz z danymi o finansowaniu i link do uchwały. Dokument źródłowy zachowuje własne oznaczenia. Urząd Publikacji UE dopuszcza ponowne wykorzystanie publikowanych w TED ogłoszeń przetargowych, z uwzględnieniem wyjątków opisanych w nocie prawnej. [Warunki TED](https://ted.europa.eu/en/legal-notice)
