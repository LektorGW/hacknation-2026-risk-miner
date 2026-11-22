"""Lock an out-of-sample cohort and predictions without interpreting outcome texts.

Run on an unchanged release with the official BZP mirror ZIP as input.
The script never passes a held-out outcome to the prediction engine.
"""
import argparse
import hashlib
import json
import lzma
import re
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "de7627c725ba9e763c2f882875e311358736b706"
ZIP_HASH = "d3b1ffd4511af2535702a87ce30f6fe9d5e546af717255497f5d6b385c17ddf8"
SEED = "riskminer-holdout-water-2026-v1"
MEMBER = "risk_miner_bzp_kopia/bzp_kopia/notices.jsonl.xz"
PLAN, AWARD, DONE, CHANGE = "ContractNotice", "TenderResultNotice", "ContractPerformingNotice", "AgreementUpdateNotice"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def norm(text):
    clean = "".join(c for c in unicodedata.normalize("NFKD", str(text or "").lower().replace("ł", "l")) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", clean))


def stream(z):
    with z.open(MEMBER) as packed, lzma.LZMAFile(packed) as source:
        for line in source:
            yield json.loads(line)


def lock_release(dest):
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", RELEASE, "riskminer", "fixtures/real/cases.json"], cwd=ROOT).decode().splitlines()
    hashes = {}
    for name in files:
        data = subprocess.check_output(["git", "show", f"{RELEASE}:{name}"], cwd=ROOT)
        p = dest / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        hashes[name] = sha(data)
    sys.path.insert(0, str(dest))
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mirror", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("release_copy", type=Path)
    args = parser.parse_args()
    protocol = args.output / "protocol.json"
    if not protocol.is_file():
        raise SystemExit("Create and commit protocol.json before running.")
    if (args.output / "lock.json").exists():
        raise SystemExit("A sealed run already exists.")
    with args.mirror.open("rb") as f:
        if hashlib.file_digest(f,"sha256").hexdigest() != ZIP_HASH:
            raise ValueError("Unexpected archive version.")
    code = lock_release(args.release_copy)
    from riskminer.analysis import default_catalog, run_backtest
    from riskminer.preview import preview_cases
    from riskminer.sectors import adapt, default_sectors
    from riskminer.sources import bzp_record, notice_text
    ref = json.loads((args.release_copy / "fixtures/real/cases.json").read_text(encoding="utf8"))
    excluded_ocid = {r["ocid"] for case in ref for r in case["records"] if r.get("ocid")}
    excluded_bzp = {r["external_id"] for case in ref for r in case["records"] if r.get("external_id")}
    excluded_names = {norm(p["title"]) for p in (c["project"] for c in ref)}
    excluded_nip = {norm(c["project"].get("nip")) for c in ref} - {""}
    index = defaultdict(lambda: {"plans": [], "types": Counter(), "numbers": set()})
    with zipfile.ZipFile(args.mirror) as z:
        for raw in stream(z):
            date = (raw.get("publicationDate") or "")[:10]
            key = raw.get("tenderId")
            if date < "2025-01-01" or not key or key in excluded_ocid:
                continue
            rec = index[key]
            typ, number = raw.get("noticeType"), raw.get("noticeNumber") or raw.get("bzpNumber")
            if not number or number in rec["numbers"]:
                continue
            rec["numbers"].add(number)
            rec["types"][typ] += 1
            if typ == PLAN and date <= "2026-03-31":
                title = norm(raw.get("orderObject"))
                eligible = (any(t in title for t in ("wodociag", "kanalizac", "oczyszczalni"))
                            and not any(t in title for t in ("dokumentacj", "nadzor"))
                            and title not in excluded_names and norm(raw.get("organizationNationalId")) not in excluded_nip)
                if eligible and re.search(r"4\.1\.8\.\).*?(?:częściowych|częściowe)\s*:\s*Nie",notice_text(raw.get("htmlBody", "")), re.I):
                    rec["plans"].append((number,date,title))
        strata = defaultdict(list)
        for key, rec in index.items():
            counts = rec["types"]
            if (len(rec["plans"]) != 1 or any(counts[t]!=1 for t in (PLAN, AWARD, DONE))
                    or excluded_bzp.intersection(rec["numbers"])):
                continue
            strata["with_change" if counts[CHANGE] else "without_change"].append(key)
        selected = []
        for stratum in ("with_change","without_change"):
            keys = sorted(strata[stratum],key=lambda key:sha(f"{SEED}|{key}".encode()))[:4]
            if len(keys) != 4:
                raise ValueError("Insufficient sample.")
            selected.extend((key,stratum) for key in keys)
        mapping = {key:f"H{i+1:02}" for i,(key,_) in enumerate(selected)}
        write(args.output/"cohort.json",{"strata_population":{s:len(v) for s,v in strata.items()},
            "sample":[{"id":mapping[k],"ocid":k,"stratum":s,"plan_number":index[k]["plans"][0][0],
                       "date":index[k]["plans"][0][1]} for k,s in selected]})
        print("Frozen OCIDs:",list(mapping.values()),flush=True)
        originals=defaultdict(list)
        for raw in stream(z):
            key=raw.get("tenderId")
            if key in mapping:
                originals[key].append(raw)
    # Only the planning notice and original release cases enter the prediction.
    reference = []
    for case in ref:
        p = dict(case["project"],id=case["project"]["project_id"],status="completed",documents=[],observations=[])
        for i,r in enumerate(case["records"]):
            sid=f"{p['id']}-source-{i:02}"
            p["documents"].append(dict(r,id=sid,status="pending"))
            p["observations"].append(dict(r,id=sid+"-obs",source_id=sid,status="pending"))
        reference.append(p)
    reference, preview_count=preview_cases(reference)
    decisions=[]
    for k,_ in selected:
        hid=mapping[k]
        plan, = [r for r in originals[k] if r["noticeType"]==PLAN]
        data=bzp_record(plan,retrieved_at="2026-11-12T12:55:53",via="https://bzp.cytr.us")
        sid=hid+"-plan"
        doc=dict(data,id=sid,status="accepted")
        p={"id":hid,"documents":[doc],"observations":[dict(data,id=hid+"-observation",source_id=sid,status="accepted")],
           "title":data["title"],"status":"planned","plan_source_id":sid}
        cut=data["published_at"][:10]
        p,cases,rules=adapt(p,reference,default_catalog(),default_sectors(),as_of=cut)
        result=run_backtest(p,cases,cut,rules,reveal=False)
        flags=[f for f in result["flags"] if f["status"]!="documented"]
        decisions.append({"id":hid,"cutoff":cut,"plan_number":data["external_id"],"title":data["title"],
            "url":data["url"],"categories":[f["category"] for f in flags],"top_three":[f["category"] for f in flags[:3]],
            "comparison_ids":[c["id"] for c in result["comparables"]],"preview_exact_links":preview_count,
            "risk_evidence":{f["category"]:[{"locator":e.get("locator"),"excerpt":e.get("excerpt")} for e in f["evidence"][:1]] for f in flags}})
        write(args.output/"plans"/(hid+".json"),{f:data[f] for f in ("external_id","title","url","ocid","published_at","text")})
    write(args.output/"predictions.json",decisions)
    independent_dir=args.output/"outcomes"
    for k,_ in selected:
        # Copy outcome/change notices verbatim to a separate blind labeling set.
        # Coordinator never prints, reads or selects any outcome using its content.
        docs=[]
        for r in originals[k]:
            if r["noticeType"] not in (DONE, CHANGE):
                continue
            data=bzp_record(r,retrieved_at="2026-11-12T12:55:53",via="https://bzp.cytr.us")
            docs.append({k:data[k] for k in ("external_id","title","kind","url","ocid","published_at","text")})
        write(independent_dir/(mapping[k]+".json"),sorted(docs,key=lambda d:d["published_at"]))
    hashes={p.relative_to(args.output).as_posix():sha(p.read_bytes()) for p in sorted(args.output.rglob("*.json"))}
    write(args.output/"lock.json",{"release":RELEASE,"frozen_at_utc":datetime.now(timezone.utc).isoformat(),
          "mirror_zip_sha256":ZIP_HASH,"release_inputs":code,"files_sha256":hashes})
    print("Prediction lock ready.",flush=True)


if __name__=="__main__":
    main()
