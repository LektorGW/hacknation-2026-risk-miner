"""Reviewable starter catalogue for the water-sector pilot.

The catalogue contains prompts for an expert. A hit is never an approved event.
The organizer's catalogue can replace this one without changing the extractor.
Signal and response terms are accent-insensitive literal stems, not regexes.
"""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


_STARTER = [
    {
        "id": "utilities",
        "title": "Kolizje z istniejącym uzbrojeniem",
        "signals": [
            "kolizj",
            "kolizyjn",
            "uzbrojeni",
            "siecią gazową",
            "sieci gazowej",
            "niezinwentaryzowan",
        ],
        "question": "Które odcinki wymagają potwierdzenia przebiegu istniejących sieci przed rozpoczęciem robót?",
        "action": "Wskaż odcinki i osobę odpowiedzialną za uzgodnienia z gestorami sieci.",
        "checks": [
            {
                "label": "Sposób weryfikacji przebiegu sieci",
                "terms": [
                    "wykonano odkryw",
                    "wykonane odkryw",
                    "potwierdzono przebieg",
                    "uzgodniono przebieg",
                ],
            },
            {
                "label": "Odpowiedzialność za uzgodnienia",
                "terms": [
                    "za uzgodnienia odpowiada",
                    "uzgodnienia przeprowadzi",
                    "odpowiedzialny za uzgodnienia",
                ],
            },
        ],
    },
    {
        "id": "continuity",
        "title": "Ciągłość pracy czynnego obiektu",
        "signals": [
            "ciągłość pracy",
            "ciągłości pracy",
            "ciągłość oczyszczania",
            "czynnej oczyszczalni",
            "czynnym obiekcie",
            "przełącze",
            "przełącza",
            "bez wyłączania",
            "bez przerw",
        ],
        "question": "Jak zostaną wykonane przełączenia i kto odpowiada za ich odbiór podczas pracy obiektu?",
        "action": "Sprawdź kolejność przełączeń i przypisz odpowiedzialność za ich przeprowadzenie.",
        "checks": [
            {
                "label": "Kolejność przełączeń",
                "terms": [
                    "kolejność przełączeń obejmuje",
                    "przełączenia w kolejności",
                    "etap 1 przełączenia",
                    "najpierw przełącz",
                    "pierwszym etapem przełączenia",
                ],
            },
            {
                "label": "Odpowiedzialność za przełączenia",
                "terms": [
                    "za przełączenia odpowiada",
                    "za przełączenie odpowiada",
                    "przełączenia wykona",
                    "przełączenie wykona",
                ],
            },
        ],
    },
    {
        "id": "ground",
        "title": "Warunki gruntowe i odwodnienie wykopów",
        "signals": ["gruntow", "geotechn", "odwodnienie wykop", "odwodnienia wykop", "wodę w wykopie"],
        "question": "Czy dla odcinków z trudnymi warunkami gruntowymi określono metodę odwodnienia?",
        "action": "Powiąż rozpoznanie podłoża z odcinkami robót i rozwiązaniem technicznym.",
        "checks": [
            {
                "label": "Rozpoznanie warunków na trasie",
                "terms": ["wykonano odwiert", "badania wykazały", "w otworze badawczym"],
            },
            {
                "label": "Metoda odwodnienia",
                "terms": [
                    "odwodnienie igłofiltr",
                    "odwodnienie za pomocą",
                    "zastosowano igłofiltr",
                    "przewidziano igłofiltr",
                ],
            },
        ],
    },
    {
        "id": "permits",
        "title": "Decyzje administracyjne i dostęp do terenu",
        "signals": ["pozwolen", "pozwoleni", "decyzj", "decyzji", "udostępnieni", "prawo do dysponowania"],
        "question": "Które pozwolenia lub uzgodnienia warunkują rozpoczęcie robót na poszczególnych odcinkach?",
        "action": "Sprawdź zakres decyzji i przyporządkuj terminy ich uzyskania do harmonogramu.",
        "checks": [
            {
                "label": "Potwierdzenie uzyskania decyzji",
                "terms": ["uzyskano pozwolenie", "wydano decyzję", "decyzja stała się ostateczna"],
            },
        ],
    },
    {
        "id": "schedule",
        "title": "Zmiana terminu wykonania",
        "signals": [
            "opóźnien",
            "opóźni",
            "wydłuż",
            "przedłuż",
            "przesunię",
            "zmianę terminu",
            "zmieniono termin",
        ],
        "question": "Które kamienie milowe ograniczają termin odbioru i jak dokumentuje się zmianę terminu?",
        "action": "Wskaż warunek zmiany harmonogramu oraz dowód wymagany do jej zatwierdzenia.",
        "checks": [
            {
                "label": "Uzgodniony termin po zmianie",
                "terms": ["nowy termin", "termin ustalono na", "termin zmieniono na"],
            },
        ],
    },
]


@lru_cache(maxsize=1)
def _knowledge():
    path = Path(__file__).with_name("knowledge") / "water.json"
    return {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))}


def expert_materials():
    """Individual cited paragraphs and table rows from the supplied DOCX files."""
    return deepcopy(list(_knowledge().values()))


def knowledge_ref(key):
    return deepcopy(_knowledge()[key])


def subsectors():
    return [knowledge_ref(f"manual-t2-r{n}")["excerpt"].split(" | ")[0] for n in range(2, 8)]


def infer_subsectors(text):
    """Literal scope indicators propose, but cannot approve, a subsector."""
    import unicodedata

    s = "".join(
        c
        for c in unicodedata.normalize("NFKD", str(text).lower().replace("ł", "l"))
        if not unicodedata.combining(c)
    )
    words = (
        ("sieci wodociag", "siec wodociag", "wodociagow", "wodociagu"),
        (
            "kanalizacji sanitar",
            "kanalizacja sanitar",
            "przepompowni sciek",
            "sieci kanalizac",
            "kanalizacji sciek",
        ),
        ("oczyszczalni",),
        ("uzdatniania wody", "ujecia wody", "studni glebin", "stacji uzdatniania"),
        ("kanalizacji deszcz", "kanalizacja deszcz", "retencyjn", "wodami opadow"),
    )
    scores = [sum(s.count(word) for word in terms) for terms in words]
    labels = subsectors()
    return [labels[i] for i in sorted(range(len(scores)), key=lambda i: -scores[i]) if scores[i]]


# Additional locally editable detection prompts, mapped to the organizer's taxonomy.
_PROMPTS = {
    1: (
        ["rozbieżn", "niespójn", "pominięt", "sprzeczn", "brak w przedmiarze"],
        "Który dokument rozstrzyga rozbieżności zakresu?",
        "Wskaż wersję obowiązującą i hierarchię dokumentacji.",
    ),
    7: (
        [
            "roboty dodatkowe",
            "robót dodatkowych",
            "roboty zamienne",
            "robót zamiennych",
            "zmieniono zakres",
        ],
        "Jak dokumentuje się konieczność i wycenę robót dodatkowych?",
        "Sprawdź uzasadnienie zmiany i sposób zatwierdzania kosztów.",
    ),
    8: (
        ["ryczałt", "kosztorysow", "waloryzac", "wynagrodzeni"],
        "Czy sposób rozliczenia uwzględnia elementy zakresu o niepewnych ilościach?",
        "Odszukaj podstawę wyceny i procedurę zmiany wynagrodzenia.",
    ),
    9: (
        ["parametr technicz", "wymagania techniczne", "równoważno", "kryterium równoważ"],
        "Jak zmierzyć zgodność rozwiązania z wymaganiami technicznymi?",
        "Wskaż wskaźnik, jednostkę i metodę pomiaru.",
    ),
    10: (
        ["rozruch", "próby końcowe", "prób końcowych", "próby szczelności", "odbiór techniczny"],
        "Jakie wyniki prób pozwolą odebrać obiekt?",
        "Sprawdź procedurę próby i odpowiedzialność za odbiór.",
    ),
    11: (
        ["odwołan", "izba odwoławcza", "unieważniono postępowanie", "ograniczenie konkurencji"],
        "Czy dokumenty wskazują sporny warunek zamówienia?",
        "Odszukaj pytania wykonawców, odpowiedzi i rozstrzygnięcia.",
    ),
    12: (
        [
            "łańcuch dostaw",
            "opóźnienie dostaw",
            "opóźnienia dostaw",
            "brak dostaw",
            "upadłość",
            "niewypłacaln",
        ],
        "Które dostawy mogą zatrzymać roboty i kto potwierdza ich dostępność?",
        "Sprawdź terminy dostaw krytycznych urządzeń.",
    ),
    13: (
        [
            "brak środków",
            "braku środków",
            "przekracza budżet",
            "brak finansowania",
            "utrata dofinansowania",
            "płatności",
        ],
        "Czy budżet i plan płatności pokrywają wskazany zakres robót?",
        "Zweryfikuj podstawę finansowania i harmonogram płatności.",
    ),
    14: (
        [
            "koszty eksploatacji",
            "kosztów eksploatacji",
            "zużycie energii",
            "zużycia energii",
            "koszt utrzymania",
        ],
        "Czy w ocenie wariantów uwzględniono zużycie energii i utrzymanie?",
        "Sprawdź założenia operatora dotyczące eksploatacji.",
    ),
    15: (
        [
            "efekt ekologiczny",
            "efektu ekologicznego",
            "jakość ścieków",
            "wydajność oczyszczania",
            "nie osiągnięto",
        ],
        "Jak zostanie potwierdzone osiągnięcie efektu użytkowego lub środowiskowego?",
        "Sprawdź wartość docelową i źródło pomiaru.",
    ),
}


def default_catalog():
    """All 15 official categories, editable signals and verbatim expert citations."""
    mapped = {2: _STARTER[2], 3: _STARTER[0], 4: _STARTER[3], 5: _STARTER[1], 6: _STARTER[4]}
    rules = []
    for n in range(1, 16):
        source = knowledge_ref(f"manual-t13-r{n + 1}")
        title, impact = source["excerpt"].split(" | ", 1)
        if n in mapped:
            rule = deepcopy(mapped[n])
            rule["aliases"] = [rule["id"]]
        else:
            signals, question, action = _PROMPTS[n]
            rule = {"signals": signals.copy(), "question": question, "action": action, "checks": []}
        rule.update(
            id=f"R{n:02}",
            title=title.split(" ", 1)[1].strip(),
            possible_impact=impact,
            enabled=True,
            expert_source=source,
        )
        clause_subject = {
            1: "wykaz rozbieżności zakresu i rozstrzygnięcia stron",
            2: "wyniki rozpoznania warunków terenowych dla wskazanych odcinków",
            3: "uzgodnienia przebiegu robót z gestorami infrastruktury i właścicielami terenu",
            4: "wykaz wymaganych decyzji, terminów i podmiotów odpowiedzialnych za ich uzyskanie",
            5: "plan przełączeń i przypisanie odpowiedzialności za utrzymanie pracy obiektu",
            6: "harmonogram z zależnościami i kamieniami milowymi",
            7: "uzasadnienie proponowanych robót dodatkowych wraz z zakresem, wyceną i wpływem na termin",
            8: "sposób wyliczenia wynagrodzenia dla pozycji o nieustalonych ilościach",
            9: "zestawienie parametrów technicznych z jednostkami i metodami ich weryfikacji",
            10: "program prób i kryteria odbioru wyników",
            11: "zestawienie wyjaśnień wymagań wpływających na sposób oceny spełnienia warunków",
            12: "harmonogram dostaw urządzeń krytycznych i potwierdzenie ich dostępności",
            13: "zestawienie płatności i wymaganych dokumentów rozliczeniowych",
            14: "zestawienie założeń zużycia energii i kosztów utrzymania",
            15: "wyniki pomiarów potwierdzających osiągnięcie parametrów wskazanych w umowie",
        }[n]
        rule["draft_clause"] = {
            "text": f"Do dnia [termin] podmiot [rola] przedkłada {clause_subject}. Odbiór dokumentuje [rola] w formie [protokół].",
            "status": "do opracowania przez eksperta",
            "source": knowledge_ref("manual-t7-r2"),
        }
        rules.append(rule)
    return rules
