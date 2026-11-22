# Sprawdzian na ośmiu nowych postępowaniach

**Risk Miner wskazał 1 z 3 kategorii ryzyka udokumentowanych po przetargu.** Spośród 40 sygnałów 1 znalazł potwierdzenie w późniejszych ogłoszeniach. To słaby wynik dla zastosowania prognostycznego. Pytania wygenerowane przez aplikację wymagają oceny merytorycznej przed podjęciem decyzji inwestycyjnej. [Wyniki dla poszczególnych postępowań](../fixtures/validation/scores.json)

## Jak zachowaliśmy rozdział danych

Badaliśmy wydanie `de7627c725ba9e763c2f882875e311358736b706`. Przed odczytaniem wyników ustaliliśmy zasady doboru próby. Z archiwum BZP wybraliśmy zakończone postępowania z publikacją pierwotną od 1 stycznia 2025 do 31 marca 2026 r. Odrzuciliśmy powtórzenia OCID, numeru ogłoszenia, znormalizowanego tytułu i NIP z pakietu 22 projektów. O kolejności wyboru decydował skrót identyfikatora. Nie sprawdzaliśmy przyczyn zdarzeń przy wyborze projektów. [Protokół doboru i oceny](../fixtures/validation/protocol.json)

W warstwie z osobnym ogłoszeniem o zmianie zakwalifikowało się 112 postępowań, a w warstwie bez takiego ogłoszenia 1 308. Z każdej wybraliśmy cztery. Jednostką pomiaru jest para postępowanie–kategoria. W H01 zakres obejmuje drogę oraz sieci, a dokumenty dotyczą dwóch umów. H07 dotyczy robót remontowych i usuwania awarii. Te różnice ograniczają możliwość przeniesienia wyników na jednorodne inwestycje budowlane. [Skład zamrożonej kohorty](../fixtures/validation/cohort.json)

Silnik otrzymał wyłącznie pierwotne ogłoszenie danego postępowania i oryginalny korpus 22 przypadków. Data publikacji planu wyznaczała granicę dostępności wcześniejszych dokumentów. Włączyliśmy roboczy podgląd powiązań po identyfikatorach. Poszczególne próby znalazły od zera do trzech porównywalnych postępowań. Zachowaliśmy również przypadek bez porównania. Główny wynik obejmuje wszystkie otwarte sygnały katalogu. Dodatkowe zestawienie obejmuje pierwsze trzy. [Przewidywania zapisane przed etykietowaniem](../fixtures/validation/predictions.json)

Wersja protokołu ma identyfikator Git `a974d9a`. Wersja `dc1cfb3` zamraża próbę, wejścia, przewidywania i dokumenty do oceny. Dopiero potem odrębny recenzent AI otrzymał 15 ogłoszeń o wykonaniu i zmianach, bez dostępu do przewidywań. Jego etykiety zamrożono w `8a3680b` przed punktacją. Skrypt sprawdza skróty danych, rozłączność kategorii i zgodność cytatów z dokumentami. **To niezależny od przewidywań odczyt techniczny wykonany przez AI. Ocena człowieka z doświadczeniem w inwestycjach wodno-kanalizacyjnych pozostaje do wykonania.** [Manifest](../fixtures/validation/lock.json) · [Etykiety i cytaty](../fixtures/validation/labels.json) · [Uwagi recenzenta](../fixtures/validation/labels-notes.md)

## Wyniki

Spośród 120 par recenzent oznaczył jedną jako niejednoznaczną. Do punktacji weszło 119. Przez FP rozumiemy sygnał, dla którego nie ma potwierdzenia realizacji w dostępnych ogłoszeniach. Żadna z 39 takich sugestii nie została w nich wyraźnie obalona. Dokumentacja zamówienia może pomijać zdarzenia znane uczestnikom inwestycji.

| Miara | Wszystkie otwarte sygnały | Pierwsze trzy pytania |
|---|---:|---:|
| Trafienia / przeoczone pozytywne kategorie | 1 / 2 | 1 / 2 |
| Sygnały bez potwierdzenia w dokumentach | 39 | 23 |
| Pary bez sygnału i bez potwierdzenia | 77 | 93 |
| Precyzja względem pozytywnych etykiet | 1/40 = 2,5% | 1/24 = 4,2% |
| Czułość względem pozytywnych etykiet | 1/3 = 33,3% | 1/3 = 33,3% |
| F1 | 4,7% | 7,4% |

Jedyny trafiony przypadek silnie wpływa na wynik. Po pominięciu kolejno jednego z ośmiu postępowań precyzja wszystkich sygnałów wynosi od 0 do 3,2%, a czułość od 0 do 50%. Są to zakresy wrażliwości na skład próby. W czterech przypadkach bez osobnego ogłoszenia o zmianie liczba dodatnich etykiet wyniosła zero, więc czułość tej warstwy jest nieokreślona. Z doboru po cztery przypadki na warstwę nie wynika częstość zdarzeń w całym sektorze. [Wyniki według warstw i przypadków](../fixtures/validation/scores.json)

| Postępowanie | Potwierdzone w źródłach | Trafione | Przeoczone | Sygnały bez potwierdzenia |
|---|---|---|---|---:|
| H01 · Krynica-Zdrój, droga i sieci | R07 | — | R07 | 6 |
| H02 · Złoty Potok, wodociąg i pompownia | R12 | — | R12 | 4 |
| H03 · Kaliski, sieć kanalizacyjna | R07 | R07 | — | 4 |
| H04 · Żmijewko, sieć kanalizacyjna | — | — | — | 3 |
| H05 · Solec nad Wisłą, kanalizacja | — | — | — | 3 |
| H06 · Pokój, wodociąg i oczyszczalnie | — | — | — | 6 |
| H07 · Giżycko, remonty kanalizacji | — | — | — | 4 |
| H08 · Zimnice Małe, włączenie studni | — | — | — | 9 |

W Kaliskach aplikacja wskazała R07. W polu 5.4 ogłoszenia `2026/BZP 00485860/01` zamawiający potwierdził zwiększenie wartości umowy z powodu prac wykraczających poza pierwotny zakres. W Krynicy-Zdroju dwa ogłoszenia opisują roboty dodatkowe, ale R07 zabrakło w przewidywaniu. W Złotym Potoku zamawiający wymienił opóźnienia dostaw materiałów, których silnik nie wskazał jako R12. Osobną wzmiankę o zmianach projektowych recenzent ocenił jako niejednoznaczną dla R07. [Kaliski](../fixtures/validation/outcomes/H03.json) · [Krynica-Zdrój](../fixtures/validation/outcomes/H01.json) · [Złoty Potok](../fixtures/validation/outcomes/H02.json)

## Ocena niezależnego eksperta branżowego

Ekspertowi należy przekazać **wyłącznie archiwum formularza**. Po rozpakowaniu otwiera lokalny plik HTML, czyta dokumenty i oznacza 15 kategorii dla każdego postępowania. Przy decyzjach dodatnich, niejednoznacznych i wyraźnie ujemnych wskazuje numer źródła oraz dosłowny cytat. Może pobrać szkic i wznowić pracę. Po zapisaniu kompletu ocen pobiera plik `ocena-eksperta.json`. Archiwum nie zawiera predykcji ani wcześniejszych etykiet. [Pusty formularz i dokumenty źródłowe dla eksperta](../deliverables/formularz-eksperta.zip)

Koordynator zachowuje otrzymany plik bez zmian i oblicza wynik osobno. Pierwsze polecenie odtwarza punktację oceny technicznej. Drugie działa po otrzymaniu niezależnej oceny człowieka.

```console
python scripts/validation_score.py fixtures/validation
python scripts/validation_score.py fixtures/validation --labels ocena-eksperta.json --output wynik-eksperta.json
```

Skrypt `scripts/validation_pack.py` odtwarza pusty formularz. Pełne powtórzenie losowania i predykcji wymaga kopii BZP o skrócie podanym w manifeście, pliku `protocol.json` skopiowanego do nowego pustego katalogu oraz obiektu Git testowanego wydania. [Skrypt zamrożenia](../scripts/validation_freeze.py) · [Kopia BZP udostępniona uczestnikom HackNation](https://bzp.cytr.us/paczka/risk_miner_bzp_kopia.zip)
