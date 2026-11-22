# Protokół technicznego oznaczania zdarzeń

Referencję przygotowuje asystent AI na podstawie zamrożonego zestawu dokumentów. Wcześniej pracował przy interfejsie Risk Minera i znał ogólną metodykę projektu. Podczas oznaczania nie otwiera wyników modelu dla odłożonej próby ani implementacji analizy. Etykiety wymagałyby odrębnej oceny człowieka, aby można je było nazwać referencją ekspercką.

Jednostką jest kontrakt lub wskazana część zamówienia. Podstawą klasyfikacji jest tabela 13 materiału organizatora „Risk_Miner_material_porady_fazy_dokumenty_ryzyka_ciekawostki.docx”. Wszystkie klasy od R01 do R15 oceniamy na podstawie materiału dostępnego dla tego kontraktu.

- **Zdarzenie udokumentowane** wymaga informacji o faktycznie zaistniałej okoliczności odpowiadającej kategorii. Podajemy źródło, sekcję i cytat. Przyczyna wymaga własnego dowodu. Sam wzrost kwoty lub późniejszy termin może mieć kilka przyczyn.
- **Niejednoznaczne** oznacza, że tekst wskazuje konkretną okoliczność istotną dla danej klasy, ale pozostawia niejasny jej charakter, zakres albo związek z realizacją. Zapis warunkowy lub przewidywanie zachowuje osobne oznaczenie od zaistniałego zdarzenia.
- **Wyraźnie zanegowane** oznacza, że źródło bezpośrednio zaprzecza wystąpieniu danego zdarzenia w rozpatrywanym zakresie.
- **Brak potwierdzenia w badanym materiale** oznacza brak odpowiedniego dowodu źródłowego. Może posłużyć jako negatyw dokumentacyjny przy ocenie ekstrakcji z tego samego materiału. Nie przesądza o faktycznym braku zdarzenia przy realizacji kontraktu.

Skutki finansowe, terminowe i formalne zapisujemy osobno. Wnioskowane lub dopuszczalne zmiany odróżniamy od zmian dokonanych. Wypłacona kwota, brak zmiany umowy czy potwierdzenie należytego wykonania same w sobie nie rozstrzygają przyczyn. Liczby pozostają w jednostce i zakresie wskazanych w źródle. Brak danych pozostaje brakiem danych.

Po zakończeniu etykietowania zapisujemy skrót SHA-256 pliku z etykietami i identyfikator próbki. Dopiero po zamrożeniu pliku analityk może przeprowadzić porównanie. Wynik dotyczy wykrywalności udokumentowanych zdarzeń w dostępnej próbie.
