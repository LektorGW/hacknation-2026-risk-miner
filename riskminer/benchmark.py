"""Rebuild the offline jury fixture from the organizer workbook and public BZP snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import lzma
import zipfile
from collections import Counter
from pathlib import Path

from .ingest import fold, load_file
from .sources import bzp_record, link_contracts, match, scope_records, _now, _bzp_number

ARCHIVE = "https://bzp.cytr.us/paczka/risk_miner_bzp_kopia.zip"


def select_rows(workbook, raw):
    ids = {r.get("bzp") for r in workbook}
    nips = {r.get("nip") for r in workbook}
    cities = {fold(r.get("location", "")) for r in workbook}
    return [
        r
        for line in raw
        if (r := json.loads(line))
        and (
            r.get("noticeNumber") in ids
            or r.get("organizationNationalId") in nips
            or fold(r.get("organizationCity", "")) in cities
        )
    ]


def build_cases(projects, records, retrieved):
    result = []
    by_number = {r.get("noticeNumber"): r for r in records}
    for p in projects:
        candidates = []
        anchor = by_number.get(p.get("bzp"))
        if anchor:
            candidates.append((anchor, "numer ogłoszenia z arkusza"))
        else:
            for raw in records:
                if raw["noticeType"] not in ("ContractNotice", "ContractPerformingNotice"):
                    continue
                if fold(raw.get("orderObject")) != fold(p["title"]):
                    continue
                if fold(raw.get("organizationName")) == fold(p["buyer"]) or raw.get(
                    "organizationNationalId"
                ) == p.get("nip"):
                    if raw["noticeType"] == "ContractNotice":
                        candidates.append((raw, "pełna nazwa przedsięwzięcia i zgodny zamawiający"))
                    elif p.get("bzp"):
                        ref = bzp_record(raw, retrieved, via=ARCHIVE).get("notice_reference")
                        if ref and _bzp_number(ref)[0] == _bzp_number(p["bzp"])[0]:
                            candidates.append(
                                (
                                    raw,
                                    "numer ogłoszenia z arkusza przywołany w sekcji III.3.2.1 ogłoszenia o wykonaniu",
                                )
                            )
        notices = {}
        for a, basis in candidates:
            # Preserve source disagreements for review. A conflicting external ID
            # is not a warrant to attach the entire unrelated procedure.
            candidate = bzp_record(a, retrieved, via=ARCHIVE)
            score, why = match(p, candidate)
            if score < 0.86:
                notices[candidate["external_id"]] = {**candidate, "confidence": score, "reasons": why}
                continue
            for raw in records:
                if raw["tenderId"] != a["tenderId"]:
                    continue
                record = bzp_record(raw, retrieved, via=ARCHIVE)
                score, reasons = match({**p, "ocid": a["tenderId"]}, record)
                record.update(
                    confidence=score, reasons=[*reasons, f"Podstawa wyboru postępowania: {basis}."]
                )
                notices[record["external_id"]] = record
        linked = link_contracts(list(notices.values()))
        observations = sorted(
            (r for r in linked if match(p, r)[0] > 0 or r.get("confidence", 0) >= 0.95),
            key=lambda r: (r["published_at"], r["external_id"]),
        )
        result.append({"project": p, "records": scope_records(observations, p)})
    return result


def write_fixture(cases, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out / "projects.csv").open("w", encoding="utf-8-sig", newline="") as f:
        keys = ["project_id", "title", "buyer", "location", "nip", "bzp", "cst", "scope", "description"]
        writer = csv.DictWriter(f, keys, extrasaction="ignore", delimiter=";")
        writer.writeheader()
        writer.writerows(c["project"] for c in cases)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("workbook", type=Path)
    p.add_argument("archive", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    projects = load_file(args.workbook.name, args.workbook.read_bytes())
    with zipfile.ZipFile(args.archive) as z:
        manifest_path = next(n for n in z.namelist() if n.endswith("/manifest.json"))
        manifest = json.loads(z.read(manifest_path))
        packed_path = str(Path(manifest_path).parent.as_posix()) + "/" + manifest["file"]
        with z.open(packed_path) as compressed:
            checksum = hashlib.file_digest(compressed, "sha256").hexdigest()
        if checksum != manifest["sha256"]:
            raise ValueError("Niezgodna suma kontrolna migawki BZP.")
        with lzma.open(z.open(packed_path), "rt", encoding="utf-8") as rows:
            raw = select_rows(projects, rows)
    cases = build_cases(projects, raw, _now())
    from .kpo import find

    for case in cases:
        case["records"].extend(find(case["project"], _now()))
    write_fixture(cases, args.out)
    print(len(cases), dict(Counter(r["kind"] for c in cases for r in c["records"])))


if __name__ == "__main__":
    main()
