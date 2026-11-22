import hashlib
import io
import json
import sqlite3

import pytest
from docx import Document
from fastapi.testclient import TestClient

from riskminer import db
from riskminer.service import app
from riskminer.cli import backup
from riskminer.workflow import add_observations


BOOK = db.ROOT / "fixtures" / "starter" / "Risk_Miner_dane_projekty.xlsx"
SAMPLE = {
    "project": {
        "title": "Budowa kanalizacji sanitarnej",
        "description": "Budowa przepompowni w rejonie kolizji istniejących sieci i wysokich wód gruntowych.",
    }
}


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setenv("RISKMINER_DB", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("RISKMINER_WORKER", "0")
    monkeypatch.delenv("RISKMINER_ENV", raising=False)
    monkeypatch.delenv("RISKMINER_ACCOUNTS", raising=False)
    with TestClient(app) as client:
        yield client


def ingest(client, path):
    res = client.post("/api/import", files={"file": (path.name, path.read_bytes())})
    assert res.status_code == 200, res.text
    return res.json()


def test_actual_workbook_repeatable_source_and_expert_change(http, tmp_path):
    res = ingest(http, BOOK)
    assert len(res["project_ids"]) == 22 and "RM-2026-002" in res["project_ids"]
    incident = next(BOOK.parent.glob("*zagrodno.pdf"))
    ingest(http, incident)
    ingest(http, BOOK)
    ingest(http, incident)
    p = http.get("/api/projects/RM-2026-002").json()
    assert len(p["documents"]) == 2
    metrics = {x["metric"]: x["value"] for x in p["measurements"]}
    assert metrics == {"requested_extension_months": 1, "expected_service_delay_months": 4}
    state = http.get("/api/state").json()
    r = next(r for r in state["reviews"] if r["kind"] == "measurements")
    assert r["status"] == "pending"
    answer = http.post("/api/reviews/" + r["id"], json={"decision": "accepted", "version": 1})
    assert answer.status_code == 200 and answer.json()["payload"]["status"] == "accepted"
    assert (
        http.post("/api/reviews/" + r["id"], json={"decision": "rejected", "version": 1}).status_code == 409
    )
    src = next(d for d in p["documents"] if d["id"] == r["source_id"])
    assert http.get(src["url"]).content == incident.read_bytes()
    assert src["published_at"] == "2026-05-05" and "strona 1" in src["locator"]
    csv = http.get("/api/export", params={"format": "csv", "project_id": p["id"]})
    assert r["source_id"] in csv.text and "requested_extension_months" in csv.text
    backup(tmp_path / "copy.db")
    with sqlite3.connect(tmp_path / "copy.db") as con:
        assert con.execute("SELECT count(*) FROM projects").fetchone()[0] == 22
        assert con.execute("SELECT count(*) FROM audit WHERE action='review'").fetchone()[0] == 1


def test_reference_trial_uses_verified_sources_and_preserves_desk(http):
    ingest(http, BOOK)
    cases = json.loads((db.ROOT / "fixtures" / "real" / "cases.json").read_text(encoding="utf-8"))
    with db.connection(True) as conn:
        for c in cases:
            add_observations(conn, c["project"]["project_id"], c["records"], "test")
    # No provisional matches are approved by a rehearsal.
    before = http.get("/api/state").json()
    p = next(p for p in before["projects"] if p["id"] == "RM-2026-001")
    assert p["procedures"] and p["contracts"] and p["observations"]
    req = {
        "project": {
            **SAMPLE["project"],
            "planned_days": 365,
            "planned_cost": 5000000,
            "metric_scope": "contract",
        },
        "filters": {"preview_links": True},
    }
    res = http.post("/api/analyze", json=req)
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["sample_size"] and result["preview_links"] and result["analysis_id"]
    for key in ("duration", "cost"):
        assert (
            result["scenario"][key]["count"] >= 3
            and result["scenario"][key]["low"] <= result["scenario"][key]["high"]
        )
    unrelated = http.post(
        "/api/analyze", json={**req, "project": {**req["project"], "metric_scope": "project"}}
    ).json()
    assert unrelated["scenario"]["duration"] is None
    assert any("Podgląd roboczy" in w for w in result["warnings"])
    assert (
        http.post(
            f"/api/analyses/{result['analysis_id']}/review", json={"decision": "accepted"}
        ).status_code
        == 422
    )
    doc = http.post("/api/brief", json={"analysis_id": result["analysis_id"]})
    assert doc.status_code == 200
    paras = "\n".join(x.text for x in Document(io.BytesIO(doc.content)).paragraphs)
    assert "Podgląd roboczy" in paras and "Karta przygotowania inwestycji" in paras
    payload = {"project_id": "RM-2026-004", "cutoff": "2025-12-02", "filters": {"preview_links": True}}
    blind = http.post("/api/replay", json=payload).json()
    assert "outcome_evidence" not in blind["replay"]
    http.put("/api/catalog", json={"rules": []}).raise_for_status()
    reveal = http.post(
        "/api/replay", json={**payload, "replay_id": blind["replay_id"], "reveal": True}
    ).json()
    assert reveal["replay"]["revealed"] and reveal["replay"]["outcome_evidence"]
    assert [x["id"] for x in blind["comparables"]] == [x["id"] for x in reveal["comparables"]]
    assert blind["flags"] == reveal["flags"]
    assert not any(x["id"] == payload["project_id"] for x in blind["comparables"])
    assert http.get("/api/state").json()["stats"]["pending"] == before["stats"]["pending"]


def test_authentication_role_separation_and_download(tmp_path, monkeypatch):
    monkeypatch.setenv("RISKMINER_ENV", "production")
    monkeypatch.setenv("RISKMINER_DB", str(tmp_path / "auth.sqlite3"))
    accts = {
        k: {"role": k, "sha256": hashlib.sha256(k.encode()).hexdigest()}
        for k in ("admin", "expert", "viewer")
    }
    monkeypatch.setenv("RISKMINER_ACCOUNTS", json.dumps(accts))
    with TestClient(app) as client:
        assert client.get("/api/state").status_code == 401
        assert client.get("/healthz").status_code == 200
        client.headers["Authorization"] = "Bearer viewer"
        assert client.get("/api/state").status_code == 200
        assert (
            client.post("/api/import", files={"file": ("a.csv", b"title;buyer\nabc;gmina")}).status_code
            == 403
        )
        client.headers["Authorization"] = "Bearer expert"
        assert client.put("/api/catalog", json={"rules": []}).status_code == 403
        client.headers["Authorization"] = "Bearer admin"
        assert (
            client.put(
                "/api/catalog", json={"rules": []}, headers={"Origin": "https://inne.example"}
            ).status_code
            == 403
        )
        assert client.get("/api/state", headers={"Host": "inne.example"}).status_code == 400
        body = client.post("/api/analyze", json=SAMPLE).json()
        decision = client.post(
            "/api/analyses/" + body["analysis_id"] + "/review", json={"decision": "accepted"}
        )
        assert decision.status_code == 200
        assert (
            client.get("/api/analyses/" + body["analysis_id"]).json()["reviews"]["all"]["actor"] == "admin"
        )


def test_invalid_workbook_rolls_back_entire_import(http):
    body = b"title;buyer\nPierwszy;JST\n;Drugi"
    assert http.post("/api/import", files={"file": ("plan.csv", body)}).status_code == 422
    assert http.get("/api/state").json()["stats"]["projects"] == 0


def test_import_typed_cost_and_duration_from_evidence(http):
    data = (
        "title;buyer;status;planned_cost;actual_cost;cost_basis;planned_days;actual_days;live_operation\n"
        "Sieć wodociągowa;Gmina;completed;1 000,00;1 100,00;brutto;100;107;tak"
    ).encode()
    res = http.post("/api/import", files={"file": ("koszty.csv", data)})
    res.raise_for_status()
    project = http.get("/api/projects/" + res.json()["project_ids"][0]).json()
    assert (project["actual_cost"], project["planned_days"], project["live_operation"]) == (1100, 100, True)
    assert project["field_sources"]["actual_cost"] == project["documents"][0]["id"]


def test_contract_reassignment_changes_breakdown_without_changing_original(http):
    ingest(http, BOOK)
    incident = next(BOOK.parent.glob("*zagrodno.pdf"))
    ingest(http, incident)
    pid = "RM-2026-002"
    case = http.get("/api/projects/" + pid).json()
    measurement = case["measurements"][0]
    with db.connection(True) as conn:
        for cid in ("first-contract", "second-contract"):
            db.put_entity(
                conn,
                pid,
                "contracts",
                dict(id=cid, title=cid, status="accepted", source_id=measurement["source_id"]),
            )
    r = next(r for r in http.get("/api/state").json()["reviews"] if r["entity_id"] == measurement["id"])
    for i, cid in enumerate(("first-contract", "second-contract"), 1):
        ans = http.post(
            "/api/reviews/" + r["id"],
            json=dict(
                version=i,
                decision="corrected",
                patch={"contract_id": cid},
                comment="Powiązanie sprawdzone z dokumentem.",
            ),
        )
        assert ans.status_code == 200, ans.text
        read = http.get("/api/projects/" + pid).json()
        counted = [
            (impact["contract_id"], m["value"])
            for impact in read["contract_impacts"]
            for m in impact["measures"]
        ]
        assert counted == [(cid, measurement["value"])]
        assert (
            next(x for x in read["documents"] if x["id"] == measurement["source_id"])["text"]
            == next(x for x in case["documents"] if x["id"] == measurement["source_id"])["text"]
        )


def test_persistent_job_queue_recovers_claim_and_runs_once(http, monkeypatch):
    from riskminer import jobs

    ingest(http, BOOK)
    with db.connection(True) as conn:
        jid = jobs.enqueue(conn, ["RM-2026-001", "RM-2026-001"], "tester")
        conn.execute("UPDATE tasks SET status='running',lease=0,attempt=1 WHERE job_id=?", (jid,))
    monkeypatch.setattr(
        "riskminer.service.enrich_one",
        lambda pid, actor: {"project_id": pid, "found": 2, "added": 0, "warnings": []},
    )
    jobs.cycle()
    job = http.get("/api/jobs/" + jid).json()
    assert job["status"] == "done" and job["total"] == job["finished"] == 1
    with db.connection() as conn:
        assert conn.execute("SELECT attempt FROM tasks WHERE job_id=?", (jid,)).fetchone()[0] == 2

def test_public_dossier_reconstructs_only_published_contract_fields(http):
    early = http.get("/pokaz", params={"sprawa": "zagrodno", "etap": 1})
    assert early.status_code == 200
    assert "00143366/01" in early.text and "00277648/01" not in early.text
    assert "3 miesiące" not in early.text and "01.06.2026" not in early.text
    second = http.get("/pokaz?sprawa=zagrodno&etap=2").text
    assert "00277648/01" in second and "00285691/01" not in second
    final = http.get("/pokaz").text
    assert "00285691/01" in final and "88 dni" in final and "różne okresy" in final
    for name in ("zlawies-wielka", "grodzisko-dolne"):
        assert "ten sam termin umowy" in http.get("/pokaz", params={"sprawa": name}).text
    for query in ("etap=0", "etap=4", "sprawa=inne"):
        assert http.get("/pokaz?" + query).status_code == 404


def test_repeated_analysis_keeps_expert_decision_and_detects_stale_review(http):
    aid = http.post("/api/analyze", json=SAMPLE).json()["analysis_id"]
    path = f"/api/analyses/{aid}/review"
    first = http.post(path, json={"decision": "rejected", "comment": "Brak potwierdzenia.", "expected_at": None})
    first.raise_for_status()
    repeated = http.post("/api/analyze", json=SAMPLE).json()
    assert repeated["analysis_id"] == aid and repeated["reviews"]["all"] == first.json()
    stale = http.post(path, json={"decision": "accepted", "expected_at": None})
    assert stale.status_code == 409
    assert http.get(f"/api/analyses/{aid}").json()["reviews"]["all"] == first.json()
    updated = http.post(path, json={"decision": "accepted", "expected_at": first.json()["at"]})
    assert updated.status_code == 200 and updated.json()["status"] == "accepted"


def test_partial_evidence_edit_keeps_other_field_sources_and_unchanged_dates(http):
    body = b"title;buyer;planned_cost;actual_cost\nBudowa;Gmina;100;120"
    res = http.post("/api/import", files={"file": ("budowa.csv", body)})
    pid = res.json()["project_ids"][0]
    url = "/api/projects/" + pid
    old = http.get(url).json()
    src = old["field_sources"]["actual_cost"]
    assert src == old["field_sources"]["planned_cost"]
    changed = http.patch(url, json={"fields": {"title": old["title"], "field_sources": {"description": src}}})
    changed.raise_for_status()
    p = http.get(url).json()
    assert p["field_sources"] == {**old["field_sources"], "description": src}
    assert "title" not in p["field_updated_at"]
    assert http.patch(url, json={"fields": {"field_sources": ["actual_cost"]}}).status_code == 422
    assert http.post("/api/replay", json={"cutoff": "2026-01-01"}).status_code == 422
