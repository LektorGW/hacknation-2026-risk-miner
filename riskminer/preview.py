"""A temporary working copy for checking exact source links before expert review."""

from .workflow import fold


def preview_cases(cases):
    copies = []
    total = 0
    for case in cases:

        def eligible(r):
            return (
                r.get("status") == "pending"
                and r.get("source") == "BZP"
                and r.get("confidence") == 0.99
                and r.get("ocid")
                and fold(case.get("nip")) == fold(r.get("buyer_identifier"))
                and case.get("bzp")
                and not r.get("quality_flags")
            )

        anchors = {
            r["ocid"]
            for r in case["observations"]
            if eligible(r) and fold(r.get("external_id")) == fold(case["bzp"])
        }
        provisional = [r for r in case["observations"] if eligible(r) and r["ocid"] in anchors]
        total += len(provisional)
        ids = {item["source_id"] for item in provisional} | {item["id"] for item in provisional}

        # Within this ephemeral copy the engine can evaluate exact-match candidates.
        # Public responses must retain the provisional designation on every reference.
        def stage(items):
            return [
                dict(r, status="accepted", review_status="accepted", provisional=True)
                if r["id"] in ids
                else r
                for r in items
            ]

        copies.append(
            {**case, "observations": stage(case["observations"]), "documents": stage(case["documents"])}
        )
    return copies, total


def mark_provisional(result, cases, count):
    refs = {r["id"] for c in cases for r in c["observations"] + c["documents"] if r.get("provisional")}

    def visit(item):
        if isinstance(item, list):
            for value in item:
                visit(value)
        elif isinstance(item, dict):
            if item.get("id") in refs:
                item["status"] = "provisional"
                item["review_status"] = "provisional"
            for value in item.values():
                visit(value)

    visit(result)
    result["preview_links"] = True
    result["warnings"].insert(
        0,
        f"Podgląd roboczy z wykorzystaniem {count} powiązań BZP po identyfikatorach w bazie. Powiązania oczekują na weryfikację człowieka.",
    )
    return result
