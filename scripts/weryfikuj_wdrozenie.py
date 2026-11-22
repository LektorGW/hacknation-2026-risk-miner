"""Read-only checks of the running instance, plus saving one example analysis."""

import argparse
import io
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile


def run(base, token, folder):
    auth = {"Authorization": "Bearer " + token}

    def call(path, body=None):
        headers = {**auth}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers
        )
        with urlopen(request, timeout=60) as r:
            return r.read()

    def timed(_):
        start = time.perf_counter()
        json.loads(call("/api/state"))
        return round(1000 * (time.perf_counter() - start))

    state = json.loads(call("/api/state"))
    target = next(p for p in state["projects"] if p["id"] == "RM-2026-002")
    assert len(state["projects"]) >= 22 and target["conflicts"]
    body = {
        "project": {
            "title": "Budowa kanalizacji sanitarnej z przepompownią",
            "description": "Gmina planuje budowę kanalizacji sanitarnej z przepompownią. Na trasie występują kolizje z uzbrojeniem i wysoki poziom wód gruntowych. Wstępny harmonogram zakłada 365 dni.",
            "type": "Sieć kanalizacji sanitarnej",
            "planned_days": 365,
            "planned_cost": 5_000_000,
            "metric_scope": "contract",
        },
        "filters": {"preview_links": True},
    }
    result = json.loads(call("/api/analyze", body))
    assert result["sample_size"] and result["flags"] and result["preview_links"]
    saved = json.loads(call("/api/analyses/" + result["analysis_id"]))
    doc = call("/api/brief", {"analysis_id": result["analysis_id"]})
    with ZipFile(io.BytesIO(doc)) as archive:
        assert "word/document.xml" in archive.namelist()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "karta-inwestycji.docx").write_bytes(doc)
    (folder / "przyklad-analizy.json").write_text(
        json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        times = list(pool.map(timed, range(12)))
    print(
        json.dumps(
            {
                "stats": state["stats"],
                "conflicts": target["conflicts"],
                "sample_size": result["sample_size"],
                "measured_contracts": result["metrics"]["actual_days"]["count"],
                "requests": len(times),
                "concurrency": 4,
                "median_ms": statistics.median(times),
                "max_ms": max(times),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8180")
    parser.add_argument("--token-file", type=Path, default=Path("var/pierwszy-dostep.txt"))
    parser.add_argument("--output", type=Path, default=Path("deliverables"))
    args = parser.parse_args()
    run(args.url, args.token_file.read_text().strip(), args.output)
