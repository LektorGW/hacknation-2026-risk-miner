# Zakres i zamrożenie referencji

Przed odczytem wyników algorytmu niezależnie oznaczono 8 postępowań i 15 ogłoszeń. Identyfikator zamrożonego zestawu to `dc1cfb3da8617f8bdb353336e22730c3a4333038`. Wszystkie odwołania w `labels.json` prowadzą do jednego z dokumentów tego zestawu. Każda etykieta dodatnia i niejednoznaczna ma dosłowny cytat, numer BZP i lokalizator. Podane w źródle daty i kwoty zachowano, włącznie z rozbieżnościami.

Przy odczycie H01 ustalono, że jeden identyfikator postępowania obejmuje dwie umowy. Koordynator doprecyzował, że porównanie pomiarowe działa na parach postępowanie–kategoria. Oznaczenie dodatnie na tym poziomie wymaga dowodu z przynajmniej jednej faktycznej umowy tego postępowania. Część `effects.contracts` zachowuje oddzielne skutki dla każdej z nich. Nie jest to osiem niezależnie zidentyfikowanych pojedynczych umów.

Znaczenie tablic `positive`, `ambiguous`, `explicit_negative` i `not_documented` opisuje protokół. Cztery tablice są rozłączne i obejmują 15 kategorii każdego postępowania. Odpowiedzi „Nie” na pytania o zmianę ceny lub „0” zmian dokumentują ściśle określony skutek lub czynność. Nie wykluczają wszystkich zdarzeń przyczynowych z danej kategorii. Dlatego pole `explicit_negative` może być puste także w kontrakcie wykonanym terminowo i bez formalnych zmian.

Oceny przyczyn i wyjaśnienia sporządził asystent AI. Przed zamrożeniem etykiet nie korzystał z predykcji dla tej kohorty. Ustalenia są techniczną referencją dokumentacyjną bez weryfikacji eksperta branżowego.

Skrót w `labels.sha256` dotyczy dokładnych bajtów UTF-8 pliku `labels.json` z zakończeniami wierszy LF w repozytorium.
