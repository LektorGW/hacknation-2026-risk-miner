# Risk Miner — analiza ryzyka inwestycji wodno-kanalizacyjnych

Narzędzie dla gmin przygotowujących przetargi. Powstało na HackNation 2026 w ramach zadania Ministerstwa Funduszy i Polityki Regionalnej. Zespół KryptoTrop.

[Panel aplikacji](https://spouse-advocate-iron-solutions.trycloudflare.com/) · [Film (1 min 54 s)](https://github.com/LektorGW/hacknation-2026-risk-miner/blob/main/deliverables/demo-risk-miner.mp4?raw=true) · [Prezentacja (8 slajdów)](deliverables/prezentacja-risk-miner.pdf)

## Problem i założenia

Gmina planuje kanalizację z przepompownią i zakłada rok na wykonanie robót. Żeby ocenić ten termin, musi odnaleźć podobne umowy, sprawdzić daty wykonania i ustalić, co zmieniło się w trakcie prac. Ogłoszenia, protokoły i aneksy opisują różne etapy tej samej inwestycji. Czasem podają sprzeczne informacje.

## Jak działa Risk Miner

1. **Odtworzenie inwestycji.** System wczytuje arkusz projektów oraz dokumenty Word i PDF, wyszukuje ogłoszenia w BZP i TED, a następnie łączy je z postępowaniami i umowami. Ekspert może otworzyć źródło, poprawić powiązanie i zapisać uzasadnienie.
2. **Ocena nowego planu.** Urzędnik podaje zakres robót, budżet i termin. Otrzymuje listę podobnych inwestycji z wyjaśnieniem doboru, porównanie kosztów i terminów oraz pytania do projektanta. Kartę można pobrać w Wordzie, a dane analizy w JSON.

## Scenariusz demonstracyjny

W aktach Zagrodna wybierz **8 czerwca 2026 r.** Ogłoszenie o wykonaniu umowy podaje trzy miesiące. Przesuń datę na **11 czerwca** i otwórz pole **4.2** w obu ogłoszeniach. Późniejszy dokument podaje dwa miesiące dla tej samej umowy. Wybierz „Pobierz kartę dowodową”, aby zachować oba cytaty, daty i odsyłacze do BZP.

W przykładowej analizie nowej kanalizacji system wskazał 14 podobnych inwestycji. Siedem umów miało porównywalne dane o terminach. Dla planu na 365 dni dało to roboczy zakres 365–442 dni. W eksporcie można sprawdzić, które umowy wpłynęły na wynik. [Przykładowy eksport JSON](deliverables/przyklad-analizy.json)

## Uruchomienie i testy

Z katalogu repozytorium, z Pythonem 3.12 i Docker Compose, wykonaj kolejno:

```sh
python -m riskminer.cli bootstrap
docker compose up -d --build
docker compose exec app python -m riskminer.cli seed
```

Akta umów są dostępne lokalnie pod `http://127.0.0.1:8180/pokaz`. Konfigurację pełnego panelu, model danych i źródła opisuje [instrukcja wdrożenia](docs/wdrozenie.md).

Testy objęły import, ponowne pobieranie ogłoszeń, decyzje eksperta i eksport. W osobnej próbie na ośmiu postępowaniach późniejsze dokumenty potwierdziły jedno z 40 ostrzeżeń. Podstawą decyzji pozostaje sprawdzenie dokumentu przez eksperta. [Raport z testów](docs/test-wydania.md) · [Wyniki próby na nowych postępowaniach](docs/test-niezalezny.md)
