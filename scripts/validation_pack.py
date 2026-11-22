"""Build a portable outcome-only form for an independent assessor."""
import hashlib
import json
import zipfile
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
SET=ROOT/"fixtures"/"validation"


def main():
    lock=json.loads((SET/"lock.json").read_text(encoding="utf8"))
    catalog=json.loads((ROOT/"riskminer"/"knowledge"/"water.json").read_text(encoding="utf8"))
    catalog={r["id"]:r for r in catalog}
    rules=[]
    for n in range(1,16):
        title,impact=catalog[f"manual-t13-r{n+1}"]["excerpt"].split(" | ",1)
        rules.append({"id":f"R{n:02}","title":title.split(" ",1)[1].strip(),"impact":impact})
    packet={"id":"riskminer-wodkan-holdout-v1","catalog":rules,"cases":[]}
    for doc in sorted((SET/"outcomes").glob("H*.json")):
        content=doc.read_bytes()
        if hashlib.sha256(content).hexdigest()!=lock["files_sha256"]["outcomes/"+doc.name]:
            raise ValueError("Outcome differs from the sealed packet.")
        packet["cases"].append({"id":doc.stem,"docs":json.loads(content)})
    if len(packet["cases"])!=8:
        raise ValueError("Incomplete cohort.")
    html=Path(__file__).with_name("validation_form.html").read_text(encoding="utf8")
    safe_json=json.dumps(packet,ensure_ascii=False).replace("<","\\u003c")
    text=html.replace("__BLIND_PACKET__",safe_json)
    dest=ROOT/"deliverables"/"formularz-eksperta.zip"
    info=zipfile.ZipInfo("formularz-eksperta.html",date_time=(2026,11,22,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(dest,"w") as z:
        z.writestr(info,text.encode("utf8"))
    print(dest.name, dest.stat().st_size)


if __name__=="__main__":
    main()
