"""Source-grounded case comparison, document checking and historical replay.

All public functions return JSON-serializable data and leave inputs unchanged.
Dates in a replay refer to publication/availability, never download timestamps.
The same engine is used for a new investment and the blind stage of a replay.
"""

import hashlib
import math
import re
import statistics
import unicodedata
from datetime import date, datetime

from .risk_rules import (
    default_catalog,
    expert_materials as expert_materials,
    infer_subsectors,
    knowledge_ref,
    subsectors,
)
from .model_provider import extract_with_provider as extract_with_provider, model_info as model_info
from .projection import planning_passage, project_view
from .sectors import classify_types


APPROVED = {"approved", "accepted", "verified", "zatwierdzony", "zatwierdzone"}
REJECTED = {"rejected", "odrzucony", "odrzucone", "superseded"}
COMPLETED = {
    "completed",
    "complete",
    "finished",
    "closed",
    "zakonczony",
    "zakonczona",
    "zrealizowany",
    "zrealizowana",
}
PLAN_KINDS = {
    "plan",
    "planning",
    "specification",
    "swz",
    "opz",
    "tender",
    "notice",
    "plan_notice",
    "tender_notice",
}
OUTCOME_KINDS = {"completion", "outcome", "performance", "completion_notice", "execution"}
FIELDS = ("planned_cost", "actual_cost", "planned_days", "actual_days")
STOP = set(
    "oraz dla przez wraz albo przy ktore ktory poprzez sprawie jest jako jego zamowienia zamowienie ogloszenie projekt inwestycja wykonanie zakresie robot budowlanych przedmiot czesc prowadzenie dokumentacja realizacja realizacji gminy gmina przetarg nie sie".split()
)
EVENT_VERBS = (
    "stwierdzono",
    "wystapil",
    "napotkano",
    "zidentyfikowano",
    "wykryto",
    "ujawniono",
    "wydluzono",
    "przedluzono",
    "przesunieto",
    "zmieniono",
    "aneksowano",
    "spowodowal",
    "doprowadzil",
    "konieczne bylo",
    "nastapil",
    "naliczono",
    "odstapiono",
    "uniewazniono",
    "zwiekszono",
    "rozwiazano",
    "poniesiono",
    "zastosowano",
    "zawarto aneks",
    "przyczyna zmiany byla",
)
UNCERTAIN = (
    "w razie",
    "w przypadku",
    "w wypadku",
    "jezeli",
    "jesli",
    "ryzyko",
    "mozliwosc",
    "moze",
    "moga",
    "potencjaln",
    "przewiduje sie",
    "nie stwierdzono",
    "nie wystap",
    "nie wykryto",
    "nie zidentyfikowano",
    "nie napotkano",
    "nie ujawniono",
    "nie wydluzono",
    "nie przedluzono",
    "nie przesunieto",
    "nie zmieniono",
    "nie spowodowal",
    "nie doprowadzil",
    "nie nastapil",
    "nie bylo",
)
UNANSWERED = (
    "nie ustalono",
    "nie okreslono",
    "brak",
    "nie wskazano",
    "nie uzgodniono",
    "nie wykonano",
    "nie uzyskano",
    "nie potwierdzono",
    "nie wydano",
    "wymaga uzupelnienia",
    "do uzgodnienia",
    "kto ",
    "czy ",
)


def _norm(value):
    value = str(value or "").lower().replace("ł", "l")
    folded = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return " ".join(folded.split())


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _cutoff(value):
    day = _date(value)
    if value is not None and day is None:
        raise ValueError("Podaj datę graniczną w formacie RRRR-MM-DD.")
    return day


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) and n >= 0 else None


def _id(obj):
    return str(obj.get("id") or obj.get("external_id") or obj.get("source_id") or "")


def _status(obj):
    return _norm(obj.get("review_status") or obj.get("status"))


def _visible(obj, day):
    if _status(obj) in REJECTED | {"pending", "uncertain", "proposed", "unverified"}:
        return False
    available = _date(obj.get("published_at") or obj.get("available_at"))
    corrected = _date(obj.get("corrected_at"))
    return day is None or (available is not None and available <= day and not (corrected and corrected > day))


def _ref(doc, excerpt=None):
    ref = {
        k: doc[k]
        for k in ("id", "title", "url", "locator", "published_at", "retrieved_at", "source", "status")
        if doc.get(k) is not None and isinstance(doc[k], (str, int, float, bool))
    }
    ref["id"] = _id(doc)
    ref["excerpt"] = str(excerpt if excerpt is not None else doc.get("excerpt") or doc.get("text") or "")[
        :1100
    ]
    return ref


def _unique(refs):
    seen = set()
    result = []
    for ref in refs:
        key = (ref.get("id"), ref.get("url"), ref.get("locator"), ref.get("excerpt"))
        if key not in seen:
            result.append(ref)
            seen.add(key)
    return result


def _docs(project):
    # Structured observations may be the only available evidence for an import.
    docs = {}
    for key in ("sources", "observations", "documents"):
        for doc in project.get(key) or []:
            if not isinstance(doc, dict) or (key == "observations" and doc.get("source_id")):
                continue
            if not _id(doc) and key == "documents" and doc.get("text"):
                src = doc.get("source")
                title = str(
                    doc.get("title") or (src.get("name") if isinstance(src, dict) else src) or "Załącznik"
                )
                locator = (
                    doc.get("locator")
                    or (src.get("locator") if isinstance(src, dict) else "")
                    or "treść załącznika"
                )
                digest = hashlib.sha256(f"{title}|{locator}|{doc['text']}".encode()).hexdigest()[:20]
                doc = {**doc, "id": "input-" + digest, "title": title, "source": title, "locator": locator}
            if _id(doc):
                docs[_id(doc)] = {**docs.get(_id(doc), {}), **doc}
    return docs


def _kind(doc):
    return _norm(doc.get("kind") or doc.get("document_type"))


def _rule_id(rule):
    return str(rule.get("category") or rule.get("id") or rule.get("title") or "")


def _catalog(catalog):
    return [
        r
        for r in (default_catalog() if catalog is None else catalog)
        if isinstance(r, dict) and _rule_id(r) and r.get("enabled", True)
    ]


def _terms(items):
    if isinstance(items, str):
        items = [items]
    return [t for t in (_norm(x).strip() for x in (items or []) if isinstance(x, str)) if t]


def _matches(normalized, terms):
    return any(t in normalized for t in terms)


def _passages(doc):
    """Offsets refer to the original plain text; preserve an exact source excerpt."""
    body = str(doc.get("text") or doc.get("body") or doc.get("excerpt") or "")
    start = 0
    for match in re.finditer(
        r"\f+|\n(?:[ \t]*\n)+|\n(?=[ \t]*[A-ZĄĆĘŁŃÓŚŹŻ0-9•–—-])|(?<=[.!?])[ \t\n]+|\Z", body
    ):
        raw = body[start : match.start()]
        excerpt = raw.strip()
        offset = start + len(raw) - len(raw.lstrip())
        start = match.end()
        if not excerpt:
            continue
        # Avoid discarding material after a very long OCR paragraph.
        for position in range(0, len(excerpt), 1000):
            sub = excerpt[position : position + 1000]
            yield sub, _norm(sub), offset + position


def _passage_ref(doc, text, offset):
    evidence = _ref(doc, text)
    offset += doc.get("offset_base", 0)
    evidence["start"] = offset
    evidence["end"] = offset + len(text)
    if not evidence.get("locator"):
        evidence["locator"] = f"znaki {offset + 1}–{offset + len(text)}"
    return evidence


def extract_events(document, catalog=None):
    """Propose documented events or conditional signals for expert review.

    A source fragment alone cannot prove causality, mitigation effectiveness or
    an event's share of a project-wide cost increase.
    """
    if _status(document) in REJECTED or not _id(document):
        return []
    rules = [
        (r, _terms(r.get("signals") or r.get("terms") or r.get("keywords"))) for r in _catalog(catalog)
    ]
    results = {}
    for text, normalized, offset in _passages(document):
        for rule, terms in rules:
            if not _matches(normalized, terms):
                continue
            if _matches(
                normalized,
                (
                    "nie stwierdzono",
                    "nie wystap",
                    "nie wykryto",
                    "nie napotkano",
                    "nie zidentyfikowano",
                    "stwierdzono brak",
                    "nie odnotowano",
                ),
            ):
                continue
            category = _rule_id(rule)
            nominal_occurrence = "wystapienie" in normalized and _matches(
                normalized, ("uniemozliwiaj", "skutkuj", "spowodow")
            )
            event_like = (_matches(normalized, EVENT_VERBS) or nominal_occurrence) and not _matches(
                normalized, UNCERTAIN
            )
            kind = "candidate_event" if event_like else "signal"
            key = (category, kind, text)
            if key in results:
                continue
            evidence = _passage_ref(document, text, offset)
            digest = hashlib.sha256(f"{_id(document)}|{category}|{kind}|{text}".encode()).hexdigest()[:20]
            results[key] = {
                "id": f"candidate-{digest}",
                "title": rule.get("title", category),
                "category": category,
                "kind": kind,
                "status": "pending",
                "description": text,
                "excerpt": text,
                "source_id": _id(document),
                "evidence": [evidence],
                "source": evidence,
                "method": "catalogue",
                "expert_source": rule.get("expert_source"),
                **_event_details(text, event_like),
            }
    return list(results.values())


def _event_details(excerpt, event_like):
    """Only explicit effects, measured in the units actually used by the source."""
    output = {
        "impact_days": None,
        "impact_cost_pln": None,
        "cause_excerpt": None,
        "mitigation_excerpt": None,
        "effectiveness_excerpt": None,
    }
    if not event_like:
        return output
    normalized = _norm(excerpt)
    delay = re.search(
        r"(?:wydluz\w*|przedluz\w*|przesuni\w*|opozn\w*)[^.;]{0,50}?\bo\s+(\d+)\s+(?:dni|doby|dob)(?!\w)",
        normalized,
    )
    if delay and not re.search(r"\b(?:do|okolo|ok\.|maksymalnie|robocz\w*)\b", delay.group()):
        if not re.match(r"\s+robocz", normalized[delay.end() :]):
            output["impact_days"] = int(delay.group(1))
    money = re.search(
        r"(?:zwieksz\w*|podwyzsz\w*|wzros\w*)[^.;]{0,45}?\bo\s+(\d{1,3}(?:[ \u00a0]\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:zl|pln)\b",
        normalized,
    )
    if money:
        output["impact_cost_pln"] = float(
            money.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
    if _matches(
        normalized, ("z powodu", "z uwagi na", "przyczyna", "wskutek", "spowodow", "ze wzgledu na")
    ):
        output["cause_excerpt"] = excerpt
    if _matches(normalized, ("wprowadzono", "zastosowano", "wykonano obejscie", "zmieniono trase")):
        output["mitigation_excerpt"] = excerpt
    if _matches(normalized, ("pozwolilo to", "dzieki temu", "w efekcie tego")):
        output["effectiveness_excerpt"] = excerpt
    return output


def _lookup_refs(raw, docs, day):
    refs = []
    if raw is None:
        return refs
    for item in raw if isinstance(raw, list) else [raw]:
        if isinstance(item, dict):
            # Identity, publication and review state belong to the stored source.
            # A cached citation captured before rejection cannot supersede it.
            doc = docs.get(_id(item), item)
        else:
            doc = docs.get(str(item), {})
        if doc and _id(doc) and _visible(doc, day):
            ref = _ref(doc)
            if (
                isinstance(item, dict)
                and item.get("excerpt")
                and item["excerpt"] in str(doc.get("text") or doc.get("excerpt") or "")
            ):
                ref["excerpt"] = item["excerpt"]
                ref["locator"] = item.get("locator") or ref.get("locator")
            refs.append(ref)
    return _unique(refs)


def _field_refs(project, name, docs, day):
    changed = _date((project.get("field_updated_at") or {}).get(name))
    if day is not None and changed and changed > day:
        return []
    by_field = project.get("field_sources") or {}
    if name in by_field:
        return _lookup_refs(by_field[name], docs, day)
    planned = name.startswith("planned")
    key = "plan_source_id" if planned else "outcome_source_id"
    return _lookup_refs(project.get(key), docs, day)


def _accepted_events(project, docs, day):
    events = []
    for e in project.get("events") or []:
        if (
            not isinstance(e, dict)
            or _status(e) not in APPROVED
            or e.get("kind") in {"signal", "hypothesis"}
        ):
            continue
        decisions = (_date(e.get(key)) for key in ("reviewed_at", "approved_at", "classified_at", "corrected_at"))
        if day is not None and any(d and d > day for d in decisions):
            continue
        refs = _lookup_refs(e.get("source_id") or e.get("evidence") or e.get("sources"), docs, day)
        if not refs:
            continue
        excerpt = e.get("excerpt")
        for ref in refs:
            source_text = (docs.get(ref["id"]) or {}).get("text") or ref["excerpt"]
            if isinstance(excerpt, str) and excerpt and excerpt in source_text:
                ref["excerpt"] = excerpt
        events.append(
            {
                "id": _id(e),
                "title": e.get("title") or e.get("category"),
                "category": str(e.get("category") or ""),
                "kind": "confirmed_event",
                "evidence": refs,
            }
        )
    return events


def _baseline(project, docs, day):
    visible = [d for d in docs.values() if _visible(d, day)]
    plan_id = str(project.get("plan_source_id") or "")
    snapshot = project.get("plan_snapshot") or {}
    source_ids = {plan_id, snapshot.get("source_id")} - {"", None}
    plan_docs = [
        d for d in visible
        if _kind(d) in PLAN_KINDS or (_id(d) in source_ids and _kind(d) not in OUTCOME_KINDS)
    ]
    if snapshot.get("lot"):
        plan_docs = [
            planning_passage(d, snapshot["lot"])
            if _id(d) == snapshot.get("source_id") or (d.get("source") == "BZP" and d.get("notice_type") == "ContractNotice")
            else d
            for d in plan_docs
        ]
    if day is None:
        if _norm(project.get("status")) not in COMPLETED and not plan_docs:
            plan_docs = visible
        return project, plan_docs
    baseline = {"id": project.get("id")}
    # project.description can be a current summary containing post-award data.
    # A replay reads only dated original material and explicitly versioned inputs.
    dated = _date(snapshot.get("published_at") or project.get("planned_at"))
    if (
        snapshot
        and dated
        and dated <= day
        and any(_id(d) == (snapshot.get("source_id") or plan_id) for d in plan_docs)
    ):
        for k in (
            "title",
            "description",
            "type",
            "sector",
            "sector_id",
            "location",
            "live_operation",
            "planned_days",
            "planned_cost",
            "currency",
            "metric_scope",
        ):
            if k in snapshot:
                baseline[k] = snapshot[k]
    for k in ("type", "sector", "location", "live_operation", "planned_days", "planned_cost"):
        # Explicit per-field citations are authoritative even when another field
        # in the mutable project record came from a later source.
        explicit = (project.get("field_sources") or {}).get(k)
        changed = _date((project.get("field_updated_at") or {}).get(k))
        if k not in baseline and (not changed or changed <= day) and _lookup_refs(explicit, docs, day):
            baseline[k] = project.get(k)
    if not baseline.get("title"):
        baseline["title"] = str(plan_docs[0].get("title") or "") if plan_docs else ""
    if not baseline.get("description"):
        baseline["description"] = "\n".join(
            str(d.get("text") or d.get("excerpt") or "")[:10000] for d in plan_docs[:8]
        )
    return baseline, plan_docs


def _tokens(text):
    words = re.findall(r"[a-z]{3,}", _norm(text))
    return {word[:6] for word in words if word not in STOP}


def _features(base, plan_docs):
    desc = " ".join(str(base.get(k) or "") for k in ("title", "description", "type"))
    scope = str((base.get("plan_snapshot") or {}).get("description") or "")
    if scope:
        source_text = scope
    else:
        source_text = " ".join(str(d.get("text") or d.get("excerpt") or "")[:3500] for d in plan_docs[:4])
    tokens = _tokens(desc)
    doc_tokens = _tokens(source_text) - tokens
    return tokens, doc_tokens


def _similarity(target, candidate, target_features, cand_features):
    reasons = []
    points = 0.0
    weights = 0.0
    meaningful = False
    official = set(subsectors())
    target_type, candidate_type = target.get("type"), candidate.get("type")
    if target_type in official and candidate_type in official and target_type != candidate_type:
        relevant = {target_type, *infer_subsectors(target.get("title") or "")}
        offered = {candidate_type, *infer_subsectors(candidate.get("title") or "")}
        if not relevant.intersection(offered):
            return 0, []
    for k, w, caption in (
        ("type", 30, "Typ inwestycji"),
        ("sector", 10, "Sektor"),
        ("live_operation", 12, "Ciągłość pracy"),
        ("location", 4, "Lokalizacja"),
    ):
        a, b = target.get(k), candidate.get(k)
        if a is None or a == "" or b is None or b == "":
            continue
        weights += w
        if _norm(str(a)) == _norm(str(b)):
            points += w
            label = ("wymagana" if a else "niewymagana") if k == "live_operation" else str(a)
            reasons.append(f"{caption}: {label}")
            meaningful |= k == "type"
        elif k == "sector":
            return 0, []
    a, a_docs = target_features
    b, b_docs = cand_features
    if (a or a_docs) and (b or b_docs):
        weights += 44
        shared = (a | a_docs) & (b | b_docs)
        v1 = {t: (1.0 if t in a else 0.2) for t in a | a_docs}
        v2 = {t: (1.0 if t in b else 0.2) for t in b | b_docs}
        cosine = sum(v1[t] * v2[t] for t in shared) / math.sqrt(
            sum(x * x for x in v1.values()) * sum(x * x for x in v2.values())
        )
        points += 44 * cosine
        if shared:
            ordered = sorted(shared, key=lambda t: (t not in a or t not in b, -len(t), t))
            source_words = re.findall(
                r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{3,}",
                str(target.get("title") or "") + " " + str(target.get("description") or ""),
            )
            spellings = {_norm(w)[:6]: w for w in source_words}
            examples = [spellings[t] for t in ordered if t in spellings][:3]
            if examples:
                reasons.append("Wspólne pojęcia w opisach: " + ", ".join(examples))
            else:
                reasons.append(f"Opisy i dokumentacja zawierają {len(shared)} wspólnych pojęć.")
            meaningful |= cosine >= 0.12
    for key, weight, label in (
        ("planned_cost", 8, "Budżet planowany"),
        ("planned_days", 8, "Planowany czas"),
    ):
        av, bv = _num(target.get(key)), _num(candidate.get(key))
        if (
            not av
            or not bv
            or (key == "planned_cost" and target.get("currency", "PLN") != candidate.get("currency", "PLN"))
        ):
            continue
        similarity = min(av, bv) / max(av, bv)
        weights += weight
        points += weight * similarity
        if similarity >= 0.75:
            reasons.append(f"{label}: zbliżona skala")
    return (round(100 * points / weights), reasons) if weights and meaningful else (0, [])


def _same_amount_basis(project):
    # A free-text description can contain both VAT bases or a word such as "internet".
    tax = set()
    for key in ("cost_basis", "cost_tax_basis", "planned_cost_tax_basis", "actual_cost_tax_basis",
                "planned_cost_basis", "actual_cost_basis"):
        words = re.findall(r"\b(?:netto|net|brutto|gross)\b", _norm(project.get(key)))
        tax.update("net" if word in {"net", "netto"} else "gross" for word in words)
    if len(tax) != 1:
        return False
    for field in ("scope", "tax_basis", "currency", "basis"):
        a, b = (project.get(f"{phase}_cost_{field}") for phase in ("planned", "actual"))
        if a or b:
            if not a or not b or _norm(a) != _norm(b):
                return False
    return True


def _case_metrics(project, docs, day):
    values = {}
    refs = {}
    for k in FIELDS:
        refs[k] = _field_refs(project, k, docs, day)
        values[k] = _num(project.get(k)) if refs[k] else None
    values["cost_change_pct"] = None
    values["days_change"] = None
    refs["cost_change_pct"], refs["days_change"] = [], []
    if values["planned_cost"] and values["actual_cost"] is not None and _same_amount_basis(project):
        deviation = (values["actual_cost"] / values["planned_cost"] - 1) * 100
        if math.isfinite(deviation):
            values["cost_change_pct"] = round(deviation, 2)
            refs["cost_change_pct"] = _unique(refs["planned_cost"] + refs["actual_cost"])
    if values["planned_days"] is not None and values["actual_days"] is not None:
        values["days_change"] = round(values["actual_days"] - values["planned_days"], 2)
        refs["days_change"] = _unique(refs["planned_days"] + refs["actual_days"])
    return values, refs


def _with_subsector(base, module=None):
    result = dict(base)
    if module:
        result["sector"] = module["name"]
        result["sector_id"] = module["id"]
        choices = {t["name"] for t in module["types"]}
        matches = classify_types(base, module)
        if result.get("type") not in choices and matches:
            result["type"] = matches[0]
        return result
    matches = infer_subsectors(result.get("title") or "") or infer_subsectors(
        result.get("description") or ""
    )
    if not result.get("type") and matches:
        result["type"] = matches[0]
    return result


def _same_project(a, b):
    # A reimport may acquire a different internal id. A buyer, title or NIP
    # is not a unique project identifier, while the organizer's project key is.
    for keys in (("id", "project_id"), ("cst", "cst_id", "cst_number"), ("project_number",)):
        a_ids = {_norm(a.get(k)) for k in keys} - {""}
        if a_ids.intersection(_norm(b.get(k)) for k in keys):
            return True
    return False


def _cohort(project, projects, target, plan_docs, day, filters):
    results = []
    seen = []
    target_features = _features(target, plan_docs)
    for other in projects:
        if not _id(other) or _same_project(project, other) or any(_same_project(other, p) for p in seen):
            continue
        other = project_view(other, as_of=day)
        if _norm(other.get("status")) not in COMPLETED:
            continue
        benchmarks = other["contract_benchmarks"]
        measured = other
        if len(benchmarks) == 1 and not any(other.get(k) is not None for k in FIELDS):
            # Use one bounded works contract as a comparable. A separate label
            # travels with every metric; nothing is rolled up to project level.
            measured = benchmarks[0]
        finished = _date(measured.get("completed_at") or measured.get("end_date"))
        if day is not None and (finished is None or finished > day):
            continue
        docs = _docs(other)
        available = [d for d in docs.values() if _visible(d, day)]
        out_refs = _lookup_refs(measured.get("outcome_source_id"), docs, day)
        if not out_refs:
            out_refs = [_ref(d) for d in available if _kind(d) in OUTCOME_KINDS]
        if not out_refs:
            out_refs = _field_refs(other, "actual_days", docs, day) or _field_refs(
                other, "actual_cost", docs, day
            )
        if day and not out_refs:
            continue
        base, planning = _baseline(other, docs, day)
        base = _with_subsector(base, other.get("_sector_module"))
        if filters.get("type") and _norm(base.get("type")) != _norm(filters["type"]):
            continue
        if (
            isinstance(filters.get("live_operation"), bool)
            and base.get("live_operation") is not filters["live_operation"]
        ):
            continue
        score, reasons = _similarity(target, base, target_features, _features(base, planning))
        if not score:
            continue
        values, refs = _case_metrics(measured, docs, day)
        registry = _lookup_refs(other.get("registry_source_id"), docs, None) if day is None else []
        evidence = _unique(
            [_ref(d) for d in planning]
            + out_refs
            + [r for items in refs.values() for r in items]
            + registry
        )
        if not evidence:
            continue
        events = _accepted_events(other, docs, day)
        results.append(
            {
                "id": _id(other),
                "title": base.get("title") or other.get("id"),
                "score": score,
                "reasons": reasons,
                "metrics": values,
                "metric_scope": measured.get("metric_scope", "project"),
                "metric_scope_label": measured.get("metric_scope_label", "całe przedsięwzięcie"),
                "metric_sources": refs,
                "evidence": evidence,
                "events": events,
                "type": base.get("type"),
                "live_operation": base.get("live_operation"),
            }
        )
        seen.append(other)
    return sorted(results, key=lambda c: (-c["score"], c["id"]))


def _summarize(cases, key, unit, scope):
    points = [
        {
            "id": c["id"],
            "title": c["title"],
            "value": c["metrics"][key],
            "sources": c["metric_sources"][key],
        }
        for c in cases
        if c["metrics"][key] is not None and c["metric_scope"] == scope
    ]
    values = [p["value"] for p in points]
    median = statistics.median(values) if values else None
    if median is not None and not math.isfinite(median):
        median = statistics.median(v / 2 for v in values) * 2
    return {
        "count": len(points),
        "unit": unit,
        "scope": scope,
        "scope_label": "umowa na roboty" if scope == "contract" else "całe przedsięwzięcie",
        "min": min(values, default=None),
        "max": max(values, default=None),
        "median": median,
        "points": points,
        "kind": "calculation",
        "interpretation": "obserwowane wartości historyczne",
    }


def _plan_bound(value, deviation, label):
    adjusted = value * (1 + deviation / 100) if label == "cost" else value + deviation
    return round(max(0, adjusted), 2) if math.isfinite(adjusted) else None


def _sensitivity(points, planned, label):
    """Keep the cohort fixed and drop each observed project once. Tied endpoints stay in the range."""
    ordered = sorted(points, key=lambda p: (p["value"], p["id"]))
    count = len(ordered) - 1
    variants = []
    for index, point in enumerate(ordered):
        low = high = None
        if count >= 3:
            low = _plan_bound(planned, ordered[1 if index == 0 else 0]["value"], label)
            high = _plan_bound(planned, ordered[-2 if index == count else -1]["value"], label)
        variants.append({"omitted_id": point["id"], "count": count, "low": low, "high": high})
    # The narrowest remaining interval identifies the largest change to either endpoint.
    return sorted(
        variants,
        key=lambda v: ((v["high"] - v["low"]) if v["low"] is not None else 0, v["omitted_id"]),
    )


def _check_documents(project, base, docs, planning, day):
    visible = list(planning)
    if day is None:
        plan_ids = {_id(d) for d in planning}
        visible.extend(d for d in docs.values() if _id(d) not in plan_ids and _visible(d, None))
        # A replay already has the dated source. Synthetic input citations are
        # reserved for the user's present-day description and title.
        description = str(base.get("description") or base.get("title") or "")
        if description:
            visible = [
                *visible,
                {
                    "id": f"input-{_id(project) or 'new'}",
                    "title": "Opis analizowanej inwestycji",
                    "source": "Dane wejściowe",
                    "text": description,
                    "locator": "opis użytkownika",
                },
            ]
        if base.get("title") and base["title"] != description:
            visible.append(
                {
                    "id": f"input-title-{_id(project) or 'new'}",
                    "title": "Nazwa analizowanej inwestycji",
                    "source": "Dane wejściowe",
                    "text": base["title"],
                    "locator": "tytuł użytkownika",
                }
            )
    return [(d, list(_passages(d))) for d in visible]


def _find_passages(documents, terms, *, answers=False):
    if not terms:
        return []
    matches = []
    for d, passages in documents:
        for excerpt, normalized, offset in passages:
            if _matches(normalized, terms) and not (
                answers and _matches(normalized, UNANSWERED + UNCERTAIN)
            ):
                matches.append(_passage_ref(d, excerpt, offset))
                break
    return _unique(matches)


def _flags(catalog, documents, cases):
    flags = []
    for rule in catalog:
        category = _rule_id(rule)
        hits = _find_passages(
            documents, _terms(rule.get("signals") or rule.get("terms") or rule.get("keywords"))
        )
        aliases = {_norm(k) for k in [category, *(rule.get("aliases") or [])]}
        precedents = [
            {"id": c["id"], "title": c["title"], "event": e}
            for c in cases
            for e in c["events"]
            if _norm(e["category"]) in aliases
        ]
        if not hits and not precedents:
            continue
        checks, missing, answers = [], [], []
        for check in rule.get("checks") or []:
            label = check.get("label") or "Informacja wymagana przez eksperta"
            found = _find_passages(documents, _terms(check.get("terms")), answers=True)
            checks.append({"label": label, "found": bool(found), "evidence": found})
            if found:
                answers.extend(found)
            else:
                missing.append(label)
        status = "documented" if checks and not missing else "partial" if answers else "open"
        flags.append(
            {
                "id": category,
                "category": category,
                "title": rule.get("title") or category,
                "kind": "hypothesis",
                "review_status": "pending",
                "status": status,
                "question": rule.get("question", ""),
                "action": rule.get("action", ""),
                "possible_impact": rule.get("possible_impact"),
                "expert_source": rule.get("expert_source"),
                "draft_clause": rule.get("draft_clause") if precedents else None,
                "evidence": hits,
                "answer_evidence": _unique(answers),
                "precedents": precedents,
                "checks": checks,
                "missing": missing,
                "comparison_count": len({p["id"] for p in precedents}),
            }
        )
    return sorted(
        flags,
        key=lambda f: (f["status"] == "documented", -bool(f["evidence"]), -f["comparison_count"], f["id"]),
    )


def _planning_checklist(base, documents):
    if base.get("sector_id") and base["sector_id"] != "water":
        return []
    types = infer_subsectors(" ".join(str(base.get(k) or "") for k in ("title", "description", "type")))
    if "Sieć wodociągowa" not in types and base.get("type") != "Sieć wodociągowa":
        return []
    checklist_terms = [
        ["niedobor", "brak dostepu do sieci", "pewnosc dostaw"],
        ["mieszkanc", "gospodarstw", "obszar obslugi"],
        ["deklaracj", "zainteresowan", "gotowosc do przylaczenia"],
        ["dlugosc", "przylacz", "trasa"],
        ["stanowisko operatora", "zasilani", "miejsce wlaczenia"],
        ["grunt", "nieruchomosc", "wlasciciel"],
        ["skrzyzowan", "kolizj", "przekroczeni"],
        ["srodowisk", "natura 2000"],
        ["odpowiedzialn", "eksploatator"],
    ]
    items = []
    for i, terms in enumerate(checklist_terms):
        source = knowledge_ref(f"guide-p{107 + i}")
        evidence = _find_passages(documents, terms)
        items.append(
            {
                "id": source["id"],
                "title": source["excerpt"],
                "expert_source": source,
                "status": "fragment_do_oceny" if evidence else "brak_fragmentu",
                "evidence": evidence,
                "review_status": "pending",
            }
        )
    return items


def analyze_project(project, projects, catalog=None, *, as_of=None, filters=None):
    day = _cutoff(as_of)
    project = project_view(project, as_of=day)
    filters = filters or {}
    docs = _docs(project)
    base, planning = _baseline(project, docs, day)
    base = _with_subsector(base, project.get("_sector_module"))
    if "_sector_module" in project and not project["_sector_module"]:
        base["sector_id"] = "unresolved"
    cases = _cohort(project, projects, base, planning, day, filters)
    documents = _check_documents(project, base, docs, planning, day)
    flags = _flags(_catalog(catalog), documents, cases)
    scope = base.get("metric_scope") or filters.get("metric_scope")
    if scope not in {"contract", "project"}:
        project_metrics = any(
            c["metric_scope"] == "project" and any(v is not None for v in c["metrics"].values())
            for c in cases
        )
        scope = (
            "project"
            if project_metrics or not any(c["metric_scope"] == "contract" for c in cases)
            else "contract"
        )
    metrics = {
        k: _summarize(cases, k, unit, scope)
        for k, unit in (("cost_change_pct", "%"), ("days_change", "dni"), ("actual_days", "dni"))
    }
    warnings = []
    if "_sector_module" in project and not project["_sector_module"]:
        warnings.append(
            "Nie ustalono sektora na podstawie dostępnych danych. Wskaż sektor lub uzupełnij opis."
        )
    if scope == "contract":
        warnings.append(
            "Zestawienie dotyczy pojedynczych umów na roboty. Kwoty oznaczają wynagrodzenie umowne i wypłacone, a czas liczony jest od zawarcia umowy."
        )
    if not cases:
        warnings.append("Brak porównywalnych zakończonych inwestycji z dostępnym źródłem.")
    if day and not planning and not base.get("description"):
        warnings.append("Brak datowanego opisu lub dokumentu wyjściowego dostępnego w dniu próby.")
    if len(cases) < 3:
        warnings.append(
            "Mniej niż trzy porównywalne przypadki. Próba jest zbyt mała do oszacowania prognozy."
        )
    for key, label in (("cost_change_pct", "odchylenia kosztu"), ("days_change", "odchylenia czasu")):
        n = metrics[key]["count"]
        if n < len(cases):
            warnings.append(
                f"Dla {label} udokumentowane i porównywalne wartości ma {n} z {len(cases)} przypadków."
            )
    schedule = metrics["actual_days"]
    planned = _num(base.get("planned_days"))
    assessment = "insufficient"
    compatible = scope == (base.get("metric_scope") or filters.get("metric_scope") or "project")
    if planned is not None and schedule["count"] >= 3 and compatible:
        assessment = (
            "below_range"
            if planned < schedule["min"]
            else "above_range"
            if planned > schedule["max"]
            else "within_range"
        )
    scenario = {"scope": scope, "cost": None, "duration": None, "reasons": []}
    for label, field, metric, unit in (
        ("cost", "planned_cost", "cost_change_pct", "PLN"),
        ("duration", "planned_days", "days_change", "dni"),
    ):
        value = _num(base.get(field))
        if not value:
            continue
        group = metrics[metric]
        if not compatible:
            scenario["reasons"].append("Zakres planu różni się od zakresu danych porównawczych.")
            break
        if group["count"] < 3:
            scenario["reasons"].append(
                f"Za mało udokumentowanych odchyleń dla jednostki {unit} (n={group['count']})."
            )
            continue
        if label == "cost" and base.get("currency", "PLN") != "PLN":
            scenario["reasons"].append("Do scenariusza kosztowego wymagany jest budżet w PLN.")
            continue
        low, high = (_plan_bound(value, group[k], label) for k in ("min", "max"))
        if low is None or high is None:
            scenario["reasons"].append(f"Wartości planu i odchyleń przekraczają zakres obliczeń ({unit}).")
            continue
        scenario[label] = {
            "low": low,
            "high": high,
            "unit": unit,
            "count": group["count"],
            "metric": metric,
            "scope": scope,
            "basis": group["scope_label"],
        }
        if day is None:
            scenario[label]["without_one"] = _sensitivity(group["points"], value, label)
    return {
        "as_of": day.isoformat() if day else None,
        "comparables": cases,
        "sample_size": len(cases),
        "scenario": scenario,
        "metrics": metrics,
        "flags": flags,
        "checklist": flags[:3],
        "metric_scope": scope,
        "sector": {"id": base.get("sector_id"), "name": base.get("sector"), "type": base.get("type")},
        "water_supply_checklist": _planning_checklist(base, documents),
        "schedule": {"planned_days": planned, "assessment": assessment, "sample_size": schedule["count"]},
        "warnings": warnings,
    }


def run_backtest(project, projects, cutoff, catalog=None, *, reveal=False, filters=None):
    day = _cutoff(cutoff)
    if day is None:
        raise ValueError("Próba historyczna wymaga daty granicznej.")
    result = analyze_project(project, projects, catalog, as_of=day, filters=filters)
    replay = {"cutoff": day.isoformat(), "revealed": bool(reveal)}
    if reveal:
        docs = _docs(project)
        observed = [
            e
            for e in _accepted_events(project, docs, None)
            if any((_date(r.get("published_at")) or date.min) > day for r in e["evidence"])
        ]
        predicted = {f["category"] for f in result["flags"] if f["status"] != "documented"}
        aliases = {
            _norm(alias): _rule_id(r)
            for r in _catalog(catalog)
            for alias in [_rule_id(r), *(r.get("aliases") or [])]
        }
        found = {aliases.get(_norm(e["category"]), e["category"]) for e in observed}
        current = project_view(project)
        measured = current
        if len(current["contract_benchmarks"]) == 1 and not any(current.get(k) is not None for k in FIELDS):
            measured = current["contract_benchmarks"][0]
        values, refs = _case_metrics(measured, docs, None)
        replay.update(
            observed=observed,
            hits=sorted(predicted & found),
            missed=sorted(found - predicted),
            unconfirmed=sorted(predicted - found),
            metrics=values,
            metric_sources=refs,
            metric_scope=measured.get("metric_scope", "project"),
            outcome_evidence=[
                _ref(d)
                for d in docs.values()
                if _visible(d, None) and (_date(d.get("published_at")) or date.min) > day
            ],
        )
    result["replay"] = replay
    return result
