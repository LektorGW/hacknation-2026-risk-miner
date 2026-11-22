# Pokaz dla jury

Kopia działa w projekcie Docker Compose `riskminer-jury`, na odrębnym wolumenie i z własnymi kontami. W środku znajdują się publiczne rekordy startowe i odtworzony przegląd techniczny trzech projektów. Automatyczne odświeżanie źródeł w tle jest wyłączone. Juror może uruchomić wyszukiwanie ręcznie, wprowadzić zmianę, przygotować analizę i pobrać kartę Word.

## Dostęp

Polecenie `python scripts/jury.py url` wyświetla bieżący adres HTTPS. Ten sam adres z dopiskiem `/materialy/` otwiera stronę z prezentacją, filmem, opisem projektu i kodem. Film, prezentację, opis, eksport oraz repozytorium można otworzyć bez logowania. Pełna przestrzeń robocza, w tym import i decyzje eksperta, wymaga tokenu z pliku operatora `var/dostep-jury/jury.txt`. Do klonowania służy `git clone https://NAZWA-TUNELU/materialy/risk-miner.git`. Archiwum ZIP zawiera to samo wydanie. Token jurora ma uprawnienia eksperta wyłącznie w kopii pokazowej.

Publiczny adres jest adresem tymczasowego tunelu Cloudflare. Komputer, Docker i tunel muszą działać podczas pokazu. Po odtworzeniu procesu tunelu operator ponownie sprawdza adres i udostępnia aktualny. Kopia lokalna jest dostępna również pod `http://127.0.0.1:8181`. [Dokumentacja Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

## Odtworzenie na nowym komputerze

Wymagane są Git, Python 3.12 i Docker Compose. W katalogu repozytorium wykonaj kolejno

```sh
python scripts/jury.py init
python scripts/jury.py materials
docker compose -f compose.jury.yaml up -d --build
docker compose -f compose.jury.yaml exec -T app python -m riskminer.cli seed
python scripts/jury.py review
python scripts/jury.py snapshot
python scripts/jury.py url
```

Token jurora i osobny token operatora są tworzone tylko przy pierwszej konfiguracji. Wzorzec SQLite znajduje się w `var/dostep-jury/baseline/start.sqlite3`. Stan po demonstracji można zastąpić tym wzorcem za pomocą `python scripts/jury.py reset`. Reset usuwa zmiany wprowadzone w kopii od chwili zapisania wzorca. Działa przy zatrzymanej aplikacji jury, przy zachowanym tunelu.

Polecenie `python scripts/sprawdz_jury.py ADRES_HTTPS` sprawdza ochronę danych, logowanie, film, ZIP i klonowanie dokładnej rewizji Git. Opcja `--reset-test` dodatkowo zapisuje próbną analizę, pobiera DOCX, wykonuje reset i sprawdza zniknięcie analizy oraz odtworzenie decyzji i historii. Po zmianie rewizji repozytorium uruchom ponownie `python scripts/jury.py materials`.
