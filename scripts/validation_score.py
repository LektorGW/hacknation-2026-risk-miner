"""Verify the blind packet, then score frozen release outputs against sealed labels."""
import argparse
import hashlib
import json
from pathlib import Path


CATEGORIES = {f"R{i:02}" for i in range(1, 16)}
GROUPS = ("positive", "ambiguous", "explicit_negative", "not_documented")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_labels(case):
    groups = {k:set(case[k]) for k in GROUPS}
    if (set().union(*groups.values()) != CATEGORIES
            or sum(len(g) for g in groups.values()) != len(CATEGORIES)):
        raise ValueError(f"Missing, overlapping or unknown labels for {case['case_id']}")
    return groups


def check_evidence(case, documents, groups):
    by_id={d["external_id"]:d for d in documents}
    backed=set()
    for entry in case.get("evidence",[]):
        found=by_id.get(entry.get("source_id"))
        quote=" ".join((entry.get("excerpt") or "").split())
        categories=entry.get("categories", [entry["category"]] if "category" in entry else [])
        if (not found or not quote or quote not in " ".join(found["text"].split())
                or (entry.get("url") and entry["url"]!=found["url"]) or set(categories)-CATEGORIES):
            raise ValueError(f"Unverified evidence in {case['case_id']}")
        backed.update(categories)
    if (groups["positive"] | groups["ambiguous"] | groups["explicit_negative"]) - backed:
        raise ValueError(f"A substantive category has no source citation in {case['case_id']}")


def per_case(predicted, labels):
    predicted = set(predicted)
    if predicted - CATEGORIES:
        raise ValueError("Invalid prediction.")
    return {"tp":sorted(predicted & labels["positive"]),
            "fn":sorted(labels["positive"] - predicted),
            "fp_explicit":sorted(predicted & labels["explicit_negative"]),
            "fp_undocumented":sorted(predicted & labels["not_documented"]),
            "tn":sorted((labels["explicit_negative"] | labels["not_documented"]) - predicted),
            "excluded":sorted(labels["ambiguous"])}


def summarize(rows):
    totals = {k:sum(len(r[k]) for r in rows) for k in ("tp","fn","fp_explicit","fp_undocumented","tn","excluded")}
    tp, fn = totals["tp"], totals["fn"]
    fp = totals["fp_explicit"] + totals["fp_undocumented"]
    def ratio(num, den):
        return round(num / den, 6) if den else None
    return {**totals,"fp":fp,"cases":len(rows),"scored_pairs":15*len(rows)-totals["excluded"],
            "precision":ratio(tp,tp+fp),"recall":ratio(tp,tp+fn),"f1":ratio(2*tp,2*tp+fp+fn)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--labels", type=Path, help="Plik JSON niezależnego eksperta.")
    parser.add_argument("--output", type=Path, help="Osobny plik wyniku dla nowych etykiet.")
    args = parser.parse_args()
    root = args.directory
    lock = read(root/"lock.json")
    for name,expected in lock["files_sha256"].items():
        if digest(root/name) != expected:
            raise ValueError(f"Sealed input differs: {name}")
    if args.labels and not args.output:
        parser.error("Dla zewnętrznych etykiet wskaż osobny --output.")
    label_file=args.labels or root/"labels.json"
    labels=read(label_file)
    if not args.labels and (root/"labels.sha256").is_file():
        if (root/"labels.sha256").read_text(encoding="utf8").split()[0].lower()!=digest(label_file):
            raise ValueError("Technical labels differ from the reviewer seal.")
    predictions={p["id"]:p for p in read(root/"predictions.json")}
    cohort={p["id"]:p for p in read(root/"cohort.json")["sample"]}
    annotations={r["case_id"]:r for r in labels["cases"]}
    if set(annotations)!=set(cohort) or set(predictions)!=set(cohort) or len(annotations)!=len(labels["cases"]):
        raise ValueError("The samples do not match.")
    results=[]
    for key in sorted(cohort):
        known=checked_labels(annotations[key])
        check_evidence(annotations[key],read(root/"outcomes"/(key+".json")),known)
        p=predictions[key]
        results.append({"id":key,"stratum":cohort[key]["stratum"],"positive":sorted(known["positive"]),
                        "prediction":p["categories"],"all":per_case(p["categories"],known),
                        "top_three":per_case(p["top_three"],known)})
    output={"lock_sha256":digest(root/"lock.json"),"labels_sha256":digest(label_file),
            "all":summarize([r["all"] for r in results]),"top_three":summarize([r["top_three"] for r in results]),
            "by_stratum":{s:summarize([r["all"] for r in results if r["stratum"]==s]) for s in {r["stratum"] for r in results}},
            "cases":results}
    omitted=[summarize([r["all"] for r in results if r["id"]!=excluded["id"]]) for excluded in results]
    output["leave_one_procedure_out"]={}
    for metric in ("precision","recall","f1"):
        values=[row[metric] for row in omitted if row[metric] is not None]
        output["leave_one_procedure_out"][metric]={"min":min(values,default=None),"max":max(values,default=None)}
    payload=json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    dest=args.output or root/"scores.json"
    if dest.exists() and dest.read_text(encoding="utf8") != payload:
        raise ValueError("Previously scored output differs. Create a new validation version.")
    if not dest.exists():
        dest.write_text(payload,encoding="utf8",newline="\n")
    print(json.dumps({k:output[k] for k in ("all","top_three","by_stratum")},indent=2))


if __name__=="__main__":
    main()
