# Zależności i źródła

Wersje pakietów Pythona w obrazie określa `constraints.txt`. Poniższe oznaczenia pochodzą z metadanych bibliotek zainstalowanych w obrazie. Pełne teksty licencji i zawiadomienia autorów znajdują się przy dystrybucjach. Kod projektu i dostarczone materiały konkursowe nie otrzymały dodatkowej licencji na publiczną redystrybucję.

| Składnik | Zastosowanie | Oznaczenie licencji |
|---|---|---|
| FastAPI, Pydantic, pydantic-core, annotated-types, annotated-doc, typing-inspection, anyio | API, walidacja i wykonywanie żądań | MIT |
| Uvicorn, Starlette, Click, idna | HTTP, serwer i narzędzia uruchomieniowe | BSD-3-Clause |
| python-multipart | Formularze i załączniki | Apache-2.0 |
| pypdf | Tekst i strony PDF | BSD-3-Clause |
| pypdfium2 i PDFium | Rasteryzacja skanów | BSD-3-Clause, Apache-2.0 i licencje składników PDFium dołączone do dystrybucji |
| Pillow | Przygotowanie obrazu dla OCR | MIT-CMU |
| python-docx, openpyxl, et_xmlfile | Odczyt Word i Excel, zapis edytowalnej karty | MIT |
| xlrd | Odczyt starszego XLS | BSD |
| lxml | XML dokumentów biurowych | BSD-3-Clause |
| httpx, httpcore | Klient HTTP używany także w testach API | BSD-3-Clause |
| h11 | Protokół HTTP | MIT |
| certifi | Certyfikaty CA | MPL-2.0 |
| typing_extensions | Typowanie | PSF-2.0 |
| opentelemetry-api | Zależność FastAPI | Apache-2.0 |
| CPython, SQLite | Runtime, trwała baza | Python Software Foundation License i warunki SQLite |
| Tesseract z polskim i angielskim modelem językowym | OCR w obrazie Linux | Apache-2.0, szczegóły w pakietach dystrybucji |
| antiword | Odczyt binarnego DOC w obrazie Linux | GPL, szczegóły w `/usr/share/doc/antiword/copyright` |
| nginx | Brama HTTPS kopii jury po stronie lokalnego serwera HTTP | [Licencja nginx](https://nginx.org/LICENSE) |
| Caddy | HTTPS na własnym serwerze instytucji | [Apache-2.0](https://github.com/caddyserver/caddy/blob/master/LICENSE) |
| cloudflared | Połączenie kopii pokazowej z siecią Cloudflare | [Apache-2.0](https://github.com/cloudflare/cloudflared/blob/master/LICENSE) |

Zdjęcie ilustracyjne pulpitu wykonano przy użyciu OpenAI ImageGen. Znak i ikonografia są elementami własnego interfejsu. Fotografia nie identyfikuje konkretnej inwestycji. Interfejs używa systemowych czcionek, lokalnych modułów JavaScript i zasobów obrazu.

W pokazie publicznym API, baza SQLite, reguły i OCR działają na stanowisku zespołu. Ruch HTTPS jurora przechodzi przez usługę Cloudflare Tunnel. Konfiguracja demonstracyjna nie określa regionu obsługi ruchu przez operatora sieci. Z lokalnego stanowiska udostępniane są publiczne akta umów, kopia Git i materiały konkursowe. Import, przegląd roboczych danych oraz decyzje eksperta wymagają konta. [Opis działania tunelu](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/)

Reguły domyślne oraz OCR działają w środowisku operatora. Tryb z własnym modelem wymaga podania modelu, jego licencji, miejsca przetwarzania i adresu usługi w konfiguracji serwera. Aplikacja udostępnia tę informację w metadanych stanu. Dane testowe, publiczne ogłoszenia i materiały organizatora mają odrębne pochodzenie. [Wykaz źródeł](../fixtures/real/README.md)
