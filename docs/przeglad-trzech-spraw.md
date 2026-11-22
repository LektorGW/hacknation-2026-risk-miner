# Przegląd trzech inwestycji

Codex sprawdził powiązania, pomiary i propozycje zdarzeń względem materiałów konkursowych i ogłoszeń źródłowych. Poniższe liczby oznaczają sugestie techniczne AI. W aplikacji wszystkie ocenione w ten sposób propozycje oczekują na decyzję człowieka. Ekspert może zweryfikować źródło, zmienić sugestię i zapisać własną ocenę.

| Inwestycja | Propozycja przyjęcia | Propozycja korekty | Propozycja odrzucenia | Do dalszej oceny |
|---|---:|---:|---:|---:|
| Zagrodno | 7 | 7 | 12 | 1 |
| Zławieś Wielka | 5 | 7 | 17 | 1 |
| Grodzisko Dolne | 4 | 4 | 6 | 0 |
| **Razem** | **16** | **18** | **35** | **2** |

Wiersz oznacza decyzję o propozycji systemu. Jedno zdarzenie może mieć kilka źródeł. Odrzucone propozycje obejmują m.in. przypadek zakwalifikowania klauzuli o ochronie danych jako nieprecyzyjnego opisu robót. Rozstrzygnięcia dotyczą treści źródeł. Ocena odpowiedzialności uczestników inwestycji wymaga dodatkowych materiałów.

**Zagrodno.** Protokół z 5 maja opisuje kolizję z siecią wodociągową w miejscu planowanej pompowni PM2 oraz wysoki poziom wód gruntowych. Dwa ogłoszenia o wykonaniu tej samej umowy podają w polu IV.4.2 odpowiednio trzy i dwa miesiące. W ogłoszeniu o wyniku w VIII.8.3 zapisano dwa miesiące. Prognoza czterech miesięcy oczekiwania na efekt użytkowy dotyczy powiązania z oczyszczalnią. Otwartą kwestią jest znaczenie klauzuli o zmianie warunków płatności dla płynności wykonawcy. Źródła BZP obejmują ogłoszenia 00089794, 00143366, 00277648 i 00285691 z 2026 r. [Protokół z Zagrodna](../fixtures/starter/Risk_Miner_protokol_konieczności_aneksowania_zagrodno.pdf)

**Zławieś Wielka.** Protokół w akapitach 20–22 proponuje przesunięcie terminu z 30 października na 5 grudnia 2025 r. i wycenia dodatkowe roboty na 151 481,54 zł brutto. Późniejsze ogłoszenie o wykonaniu potwierdza nowy termin i kwotę zmiany. W protokole podano datę podpisania umowy 14 lutego, w ogłoszeniach o wyniku i wykonaniu 14 lipca. Do ustalenia właściwej daty potrzebna jest podpisana umowa. Dla oceny zasadności ryczałtu istotne są również oględziny filtrów i dane dostępne przed zamówieniem. Źródła BZP obejmują ogłoszenia 00245492 i 00342797 z 2025 r. oraz 00021981 z 2026 r. [Protokół gminy Zławieś Wielka](../fixtures/starter/Risk_Miner_protokol_koniecznosci_zławieś.docx)

**Grodzisko Dolne.** Pismo RI.041.1.2025 zawiera prośbę gminy o wydłużenie przedsięwzięcia KPO do 31 grudnia 2025 r. Wykonanie kontraktu na roboty odnotowano w BZP 30 grudnia. To dwa różne zakresy i dwa różne dowody. W nagłówku pisma i w arkuszu startowym zapisano różne numery NIP. Powiązanie z projektem wspierają numer przedsięwzięcia i tytuł. Do sprawdzenia pozostaje odpowiedź instytucji finansującej i identyfikator podmiotu. Źródła BZP obejmują ogłoszenia 00211437 i 00347687 z 2025 r. oraz 00004536 z 2026 r. [Pismo gminy](../fixtures/starter/Risk_Miner_pismo_termin_grodzisko.pdf)

**Odtworzenie.** W głównej bazie odnotowano 71 wpisów. W świeżej kopii demonstracyjnej parser zawarł dwie wypowiedzi o przyłączu i czteromiesięcznym oczekiwaniu w jednym cytacie. Kopia zawiera 70 wpisów, w tym 17 korekt. Każda zastosowana decyzja wymaga zgodności identyfikatorów, wersji i skrótu SHA-256 tekstu źródła. Ponowne uruchomienie pomija już odtworzone decyzje. Powiązanie obu wariantów zapisano w manifeście. [Manifest decyzji](decyzje-trzech-spraw.json) · [Odtworzenie i kontrola](../scripts/przeglad_spraw.py)
