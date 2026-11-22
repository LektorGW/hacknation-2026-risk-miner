"""Read-only projections of accepted BZP evidence. No contract totals a project."""

import re
from collections import defaultdict
from datetime import date

from .risk_rules import infer_subsectors


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _accepted(project, cutoff):
    docs = {d.get("id"): d for d in project.get("documents") or []}
    for record in project.get("observations") or []:
        doc = docs.get(record.get("source_id"))
        if (
            record.get("status") != "accepted"
            or not doc
            or doc.get("status") != "accepted"
            or record.get("source") != "BZP"
        ):
            continue
        available = _day(doc.get("published_at"))
        if not available or (cutoff and available > cutoff):
            continue
        # Public historical facts may be transcribed retrospectively. An expert
        # intervention changing the link or content is available only afterwards.
        corrections = (_day(item.get("corrected_at")) for item in (record, doc))
        if cutoff and any(d and d > cutoff for d in corrections):
            continue
        yield record, doc


def field_reference(doc, code, body=None):
    text = (doc.get("text") or "") if body is None else body
    block = re.search(
        r"(?im)^" + re.escape(code) + r"\.\)[^\n]*(?:\n(?!\s*\d+\.\d+\.\)|SEKCJA|Część)\S[^\n]*)?", text
    )
    ref = {
        "id": doc["id"],
        "title": doc.get("title"),
        "url": doc.get("url"),
        "published_at": doc.get("published_at"),
        "retrieved_at": doc.get("retrieved_at"),
        "locator": "BZP, pole " + code,
        "excerpt": block.group().strip() if block else "",
    }
    return ref


def _lot_scope(project):
    match = re.fullmatch(r"\s*część\s+(\d+)\s*", str(project.get("scope") or ""), re.I)
    return match[1] if match else ""


def _lot_section(text, lot):
    return re.search(
        r"(?im)^Część\s+" + re.escape(str(lot)) + r"\s*$\n([\s\S]*?)(?=^Część\s+\d+\s*$|^SEKCJA\s+V|\Z)",
        text,
    )


def _scope_text(text):
    match = re.search(r"(?im)^4\.2\.2\.\)\s*[^\n]*\n([\s\S]*?)(?=^4\.2\.\d+\.\)|^SEKCJA\s|\Z)", text)
    return match[1].strip()[:12000] if match else ""


def _planning_result(record, doc, lot):
    body = planning_passage(doc, lot).get("text") or ""
    description = _scope_text(body)
    title = doc.get("title") or record.get("title") or ""
    snapshot = {
        "source_id": doc["id"],
        "title": title,
        "description": description,
        "lot": lot,
        "published_at": doc["published_at"],
        "metric_scope": "contract",
    }
    types = infer_subsectors(title) or infer_subsectors(description)
    if types:
        snapshot["type"] = types[0]
        snapshot["secondary_types"] = types[1:]
    period = re.search(r"(?im)^4\.2\.10\.\)[^\n]*?:\s*(\d+)\s+dn\w*\s*$", body)
    if period:
        snapshot["planned_days"] = int(period[1])
    return snapshot


def planning_passage(doc, lot):
    """Restrict a multi-lot tender to the selected record's part and original offsets."""
    if not lot:
        return doc
    full = doc.get("text") or ""
    match = _lot_section(full, lot)
    section = match[1] if match else ""
    return {
        **doc,
        "text": section,
        "body": section,
        "excerpt": section,
        "offset_base": match.start(1) if match else 0,
        "locator": f"BZP, część {lot}",
    }


def _award_body(doc, lot):
    chunks = list(
        re.finditer(r"(?im)^SEKCJA VIII\s+UMOWA(?:\s+\(dla części\s+(\d+)\))?\s*$", doc.get("text", ""))
    )
    for chunk in chunks:
        if (chunk[1] or "") == (lot or ""):
            return re.split(
                r"(?im)^SEKCJA [IVX]+\s|^Część \d+\s*$", doc["text"][chunk.end() :], maxsplit=1
            )[0]
    return doc.get("text", "") if not chunks and not lot else ""


def project_view(project, *, as_of=None):
    """Produce contract-level benchmarks and original planning snapshots.

    Existing verified project-wide measurements remain independent. When a record
    covers several contracts, each stays inspectable and no combined duration or
    budget is manufactured. Retrieval timestamps never determine a cutoff.
    """
    cutoff = _day(as_of)
    if as_of is not None and cutoff is None:
        raise ValueError("Nieprawidłowa data projekcji.")
    result = dict(project)
    pairs = list(_accepted(project, cutoff))
    result["contract_benchmarks"] = []
    result["projection_warnings"] = []
    result["projection_conflicts"] = []
    if not pairs:
        return result
    lot = _lot_scope(project)
    plans = [
        (r, d)
        for r, d in pairs
        if r.get("kind") == "notice" and r.get("notice_type") in (None, "ContractNotice")
    ]
    procs = {r.get("ocid") or r.get("procedure_key") for r, _ in plans}
    if plans and len(procs) == 1:
        plan, plan_doc = min(plans, key=lambda pair: pair[1]["published_at"])
        snapshot = _planning_result(plan, plan_doc, lot)
        if not project.get("plan_snapshot"):
            result["plan_snapshot"] = snapshot
            result.setdefault("plan_source_id", plan_doc["id"])
            result.setdefault("planned_at", plan_doc["published_at"][:10])
        if not project.get("type") and snapshot.get("type"):
            result["type"] = snapshot["type"]
            result["type_source_id"] = plan_doc["id"]
            result["type_status"] = "proposed"
    awards = defaultdict(list)
    completions = defaultdict(list)
    for r, doc in pairs:
        if r.get("kind") == "award":
            for award in r.get("awards") or []:
                key = award.get("contract_key")
                if key and (not lot or lot == award.get("lot")):
                    awards[key].append((award, doc))
        if (
            r.get("kind") == "completion"
            and r.get("contract_key")
            and not r.get("quality_flags")
            and (not lot or lot == r.get("lot"))
        ):
            completions[r["contract_key"]].append((r, doc))
    for key, award_items in awards.items():
        if len(award_items) != 1 or key not in completions:
            continue
        award, award_doc = award_items[0]
        outcomes = completions[key]
        fields = ("signed_on", "finished_on", "actual_days", "paid_pln")
        measured = {tuple((r.get("facts") or {}).get(k) for k in fields) for r, _ in outcomes}
        if len(measured) != 1:
            result["projection_warnings"].append(
                "Sprzeczne ogłoszenia o wykonaniu tej samej umowy. Pomiary wymagają weryfikacji."
            )
            for field, code in (("signed_on", "4.1"), ("finished_on", "5.2"), ("paid_pln", "5.5")):
                variants = [
                    dict(value=r.get("facts", {}).get(field), source=field_reference(d, code)) for r, d in outcomes
                ]
                if len({v["value"] for v in variants}) > 1:
                    result["projection_conflicts"].append(
                        {"field": field, "contract_key": key, "variants": variants}
                    )
            continue
        completion, out_doc = max(outcomes, key=lambda x: x[1]["published_at"])
        facts = completion.get("facts") or {}
        start, end = _day(facts.get("signed_on")), _day(facts.get("finished_on"))
        if (
            not start
            or not end
            or start > end
            or end > _day(out_doc["published_at"])
            or (cutoff and end > cutoff)
            or award.get("signed_on") != facts.get("signed_on")
            or (
                award.get("contract_value_pln") is not None
                and facts.get("contract_value_pln") is not None
                and award["contract_value_pln"] != facts["contract_value_pln"]
            )
        ):
            result["projection_warnings"].append(
                "Rozbieżne daty lub wartości dla pary ogłoszeń. Pomiary wymagają weryfikacji."
            )
            continue
        contract_lot = award.get("lot") or ""
        award_body = _award_body(award_doc, contract_lot)
        refs = {
            "planned_cost": field_reference(award_doc, "8.2", award_body),
            "actual_cost": field_reference(out_doc, "5.5"),
            "planned_days": [field_reference(award_doc, "8.1", award_body), field_reference(award_doc, "8.3", award_body)],
            "actual_days": [field_reference(out_doc, "4.1"), field_reference(out_doc, "5.2")],
        }
        # A numeric observation may outlive the locally available text of its
        # form field. Never substitute an adjacent lot or a generic document link.
        absent = [
            field for field, source in refs.items()
            if not all(ref["excerpt"] for ref in (source if isinstance(source, list) else [source]))
        ]
        entry = {
            "contract_key": key,
            "lot": contract_lot,
            "metric_scope": "contract",
            "metric_scope_label": "umowa na roboty" + (f" · część {contract_lot}" if contract_lot else ""),
            "cost_basis": "PLN brutto, wynagrodzenie umowne",
            "planned_cost": award.get("contract_value_pln"),
            "actual_cost": facts.get("paid_pln"),
            "planned_days": award.get("planned_days"),
            "actual_days": (end - start).days,
            "signed_on": start.isoformat(),
            "completed_at": end.isoformat(),
            "field_sources": refs,
            "source_ids": [award_doc["id"], out_doc["id"]],
            "outcome_source_id": out_doc["id"],
            "eligible": True,
            "warnings": [],
        }
        if absent:
            for field in absent:
                entry[field] = None
                refs[field] = []
            entry["warnings"].append("W zachowanym fragmencie ogłoszenia brak pól źródłowych dla części pomiarów.")
        periods = [
            dict(
                value=r.get("facts", {}).get("agreed_period"),
                days=r.get("facts", {}).get("planned_days"),
                source=field_reference(d, "4.2"),
            )
            for r, d in outcomes
        ]
        if any(
            v["days"] is not None
            and entry["planned_days"] is not None
            and v["days"] != entry["planned_days"]
            for v in periods
        ):
            entry["warnings"].append(
                "Termin opisany przy wykonaniu różni się od pierwotnej umowy. Podstawą porównania jest publikacja o udzieleniu zamówienia."
            )
            entry["period_evidence"] = {
                "original": {
                    "value": award.get("agreed_period"),
                    "source": field_reference(award_doc, "8.3", award_body),
                },
                "completion": periods,
            }
        if len({p["days"] for p in periods if p["days"] is not None}) > 1:
            result["projection_warnings"].append(
                "Ogłoszenia o wykonaniu tej samej umowy podają różne okresy realizacji. Pierwotny termin pochodzi z ogłoszenia o udzieleniu zamówienia."
            )
            result["projection_conflicts"].append(
                {"field": "agreed_period", "contract_key": key, "variants": periods}
            )
        result["contract_benchmarks"].append(entry)
    if len(result["contract_benchmarks"]) > 1:
        result["projection_warnings"].append(
            "Kilka umów w jednym projekcie. Każda ma osobny zakres kosztów i terminów."
        )
    return result
