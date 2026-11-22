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
    ids = {_bzp_number(r.get("bzp"))[0] for r in workbook} - {""}
    nips = {str(r["nip"]).strip() for r in workbook if r.get("nip")} - {""}
    cities = {fold(r.get("location") or "") for r in workbook} - {""}
    return [
        r
        for line in raw
        if (r := json.loads(line))
        and (
            str(r.get("organizationNationalId") or "").strip() in nips
            or fold(r.get("organizationCity") or "") in cities
            or _bzp_number(r.get("noticeNumber") or r.get("bzpNumber"))[0] in ids
        )
    ]


def build_cases(projects, records, retrieved):
    result = []
    records = [r for r in records if r.get("noticeNumber") or r.get("bzpNumber")]
    by_number = {}
    for raw in records:
        number, version = _bzp_number(raw.get("noticeNumber") or raw.get("bzpNumber"))
        if number:
            by_number.setdefault(number, []).append((version, raw))
    for p in projects:
        candidates = []
        number, version = _bzp_number(p.get("bzp"))
        for revision, anchor in by_number.get(number, []):
            if not version or version == revision:
                candidates.append((anchor, "numer ogłoszenia z arkusza"))
        if not candidates:
            for raw in records:
                if raw.get("noticeType") not in ("ContractNotice", "ContractPerformingNotice"):
                    continue
                if not p.get("title") or fold(raw.get("orderObject") or "") != fold(p["title"]):
                    continue
                if (p.get("buyer") and fold(raw.get("organizationName") or "") == fold(p["buyer"])) or (
                    p.get("nip") and str(raw.get("organizationNationalId") or "").strip() == str(p["nip"]).strip()
                ):
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
            procedure = a.get("tenderId")
            related = (r for r in records if r.get("tenderId") == procedure) if procedure else [a]
            for raw in related:
                record = bzp_record(raw, retrieved, via=ARCHIVE)
                score, reasons = match({**p, "ocid": procedure}, record)
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
