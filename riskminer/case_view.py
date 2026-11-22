"""Case-level reconciliation shown in the desk without changing source records."""

from collections import defaultdict
from .projection import field_reference, project_view


def detailed_view(raw):
    p = project_view(raw)
    documents = {d["id"]: d for d in p["documents"]}
    groups = defaultdict(list)
    for r in p["observations"]:
        if (r.get("kind") == "completion" and r.get("contract_key")
                and r.get("status") != "rejected"
                and documents.get(r.get("source_id"), {}).get("status") != "rejected"):
            groups[r["contract_key"]].append(r)
    p["conflicts"] = []
    for contract, items in groups.items():
        for field, title, code in (
            ("planned_days", "Okres realizacji umowy", "4.2"),
            ("paid_pln", "Wypłacone wynagrodzenie", "5.5"),
            ("finished_on", "Data wykonania", "5.2"),
        ):
            variants = []
            for r in items:
                facts = r.get("facts", {})
                if facts.get(field) is None:
                    continue
                variant = dict(
                    value=r["facts"][field],
                    source_id=r["source_id"],
                    source=r["external_id"],
                    url=r.get("url"),
                    status=r["status"],
                )
                if field == "planned_days" and facts.get("agreed_period"):
                    variant["source_period"] = facts["agreed_period"]
                document = documents.get(r["source_id"])
                if document:
                    ref = field_reference(document, code)
                    if ref["excerpt"]:
                        variant["field_reference"] = {**ref, "title": r["external_id"]}
                variants.append(variant)
            if len({v["value"] for v in variants}) > 1:
                p["conflicts"].append(
                    dict(contract_key=contract, field=field, title=title, variants=variants)
                )
    p["contract_impacts"] = []
    for c in p["contracts"]:
        group = dict(contract_id=c["id"], title=c["title"])
        for label, source in (("events", "events"), ("measures", "measurements"), ("changes", "changes")):
            group[label] = [
                {
                    k: r[k]
                    for k in ("id", "title", "value", "unit", "status", "source_id", "fact_type")
                    if k in r
                }
                for r in p[source]
                if r.get("status") == "accepted" and r.get("contract_id") == c["id"]
            ]
        p["contract_impacts"].append(group)
    return p
