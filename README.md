# Risk Miner

Projekt zespołu KryptoTrop na HackNation 2026. Risk Miner porównuje inwestycje wodno-kanalizacyjne, wskazuje rozbieżności w dokumentach i przygotowuje pytania do projektanta przed przetargiem.

- [Prezentacja (PDF, 8 slajdów)](deliverables/prezentacja-risk-miner.pdf)
- [Film demonstracyjny (1 min 54 s)](deliverables/demo-risk-miner.mp4)
- [Aplikacja demonstracyjna](https://spouse-advocate-iron-solutions.trycloudflare.com/) · dostęp z tokenem jury

## Uruchomienie lokalne

Wymagane są Python 3.12 i Docker Compose.

```sh
python -m riskminer.cli bootstrap
docker compose up -d --build
docker compose exec app python -m riskminer.cli seed
```

Otwórz `http://127.0.0.1:8180`. Token znajdziesz w `var/pierwszy-dostep.txt`.
