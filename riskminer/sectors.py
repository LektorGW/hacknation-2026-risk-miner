"""Editable sector selection and catalogue routing for the planning engine."""

import re
import unicodedata
from copy import deepcopy

from .risk_rules import knowledge_ref, subsectors


def _norm(value):
    raw = unicodedata.normalize("NFKD", str(value or "").lower().replace("ł", "l"))
    return " ".join(re.findall("[a-z0-9]+", "".join(c for c in raw if not unicodedata.combining(c))))


def default_sectors():
    terms = [
        ["sieci wodociąg", "sieć wodociąg", "wodociągow", "wodociągu"],
        ["kanalizacji sanitar", "kanalizacja sanitar", "przepompowni ściek", "sieci kanalizac"],
        ["oczyszczalni"],
        ["uzdatniania wody", "ujęcia wody", "studni głębin"],
        ["kanalizacji deszcz", "kanalizacja deszcz", "retencyjn", "wodami opadow"],
        [],
    ]
    return [
        {
            "id": "water",
            "name": "Gospodarka wodno-ściekowa",
            "description": "Infrastruktura zaopatrzenia w wodę, kanalizacji, retencji i oczyszczania ścieków.",
            "aliases": ["wodno-kanalizacyjny", "wod-kan", "wodno-ściekowy", "wodociągowo-kanalizacyjny"],
            "types": [
                {"name": name, "terms": clues, "source": knowledge_ref(f"manual-t2-r{i + 2}")}
                for i, (name, clues) in enumerate(zip(subsectors(), terms))
            ],
        }
    ]


def validate_sectors(sectors):
    if not isinstance(sectors, list) or not sectors or len(sectors) > 100:
        raise ValueError("Podaj listę od 1 do 100 sektorów.")
    ids, labels = set(), set()

    def items(value, limit):
        return (
            isinstance(value, list)
            and len(value) <= limit
            and all(isinstance(s, str) and 0 < len(s.strip()) <= 250 and _norm(s) for s in value)
        )

    for s in sectors:
        if not isinstance(s, dict):
            raise ValueError("Każdy sektor musi mieć nazwę i identyfikator.")
        key, name, desc = s.get("id"), s.get("name"), s.get("description", "")
        if (
            not isinstance(key, str)
            or not re.fullmatch("[a-z0-9][a-z0-9_-]{0,63}", key)
            or key in ids
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 160
            or not isinstance(desc, str)
            or len(desc) > 5000
            or not items(s.get("aliases", []), 80)
        ):
            raise ValueError("Sprawdź nazwę, identyfikator, opis i aliasy sektora.")
        ids.add(key)
        names = {_norm(v) for v in [key, name, *s.get("aliases", [])]}
        if names & labels:
            raise ValueError("Nazwa lub alias wskazuje więcej niż jeden sektor.")
        labels.update(names)
        types = s.get("types")
        if not isinstance(types, list) or not types or len(types) > 150:
            raise ValueError("Sektor wymaga przynajmniej jednego typu inwestycji.")
        unique = set()
        for t in types:
            label = t.get("name") if isinstance(t, dict) else None
            if (
                not isinstance(label, str)
                or not label.strip()
                or len(label) > 200
                or _norm(label) in unique
                or not items(t.get("terms", []), 120)
            ):
                raise ValueError("Każdy typ wymaga unikatowej nazwy oraz listy fragmentów tekstu.")
            unique.add(_norm(label))
    return deepcopy(sectors)


def classify_types(base, module):
    title, body = _norm(base.get("title")), _norm(base.get("description"))
    ranked = []
    for index, item in enumerate(module.get("types", [])):
        terms = [_norm(t) for t in [item["name"], *item.get("terms", [])]]
        scores = [(term in title, term in body) for term in terms if term]
        score = (sum(1 for a, _ in scores if a), sum(1 for _, b in scores if b))
        if any(score):
            ranked.append((score, -index, item["name"]))
    return [r[2] for r in sorted(ranked, reverse=True)]


def _resolve(base, sectors, *, missing_default=False):
    marked = base.get("sector_id") or base.get("sector")
    if marked:
        label = _norm(marked)
        return next(
            (
                s
                for s in sectors
                if label in {_norm(x) for x in [s["id"], s["name"], *s.get("aliases", [])]}
            ),
            None,
        )
    label = _norm(base.get("type"))
    typed = [s for s in sectors if label and label in {_norm(t["name"]) for t in s["types"]}]
    if len(typed) == 1:
        return typed[0]
    matches = [s for s in sectors if classify_types(base, s)]
    if len(matches) == 1:
        return matches[0]
    if not matches and missing_default and len(sectors) == 1:
        return sectors[0]
    return None


def _rules(module, rules):
    return [r for r in rules if module and module["id"] in (r.get("sector_ids") or ["water"])]


def rules_for_sector(project, rules, sectors):
    module = _resolve(project, sectors, missing_default=True)
    return _rules(module, rules)


def adapt(project, cases, rules, sectors, *, as_of=None):
    """Select comparable cases and rules without rewriting persisted project data."""
    from .analysis import _baseline, _cutoff, _docs
    from .projection import project_view

    day = _cutoff(as_of)

    def select(p):
        if day is None:
            return _resolve(p, sectors, missing_default=True)
        view = project_view(p, as_of=day)
        snapshot, _ = _baseline(view, _docs(view), day)
        return _resolve(snapshot, sectors)

    module = select(project)
    target = {**project, "_sector_module": module}
    if not module:
        return target, [], []
    group = []
    for candidate in cases:
        choice = select(candidate)
        if choice and choice["id"] == module["id"]:
            group.append({**candidate, "_sector_module": module})
    return target, group, _rules(module, rules)
