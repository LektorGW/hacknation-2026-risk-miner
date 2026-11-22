import copy
import json
from pathlib import Path

import pytest

from riskminer.analysis import analyze_project, run_backtest
from riskminer.case_view import detailed_view
from riskminer.projection import project_view


@pytest.fixture(scope="module")
def official_records():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "real" / "cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def reviewed(record):
    p = {
        **record["project"],
        "id": record["project"]["project_id"],
        "status": "completed",
        "documents": [],
        "observations": [],
    }
    for i, observation in enumerate(record["records"]):
        sid = f"{p['id']}-doc-{i}"
        p["documents"].append(dict(observation, id=sid, status="accepted"))
        p["observations"].append(dict(observation, id=f"obs-{i}", status="accepted", source_id=sid))
    return p


def test_contract_is_not_total_project_and_has_exact_form_fields(official_records):
    p = reviewed(official_records[7])
    dry = copy.deepcopy(p)
    view = project_view(p)
    assert "planned_cost" not in view and "actual_cost" not in view
    (b,) = view["contract_benchmarks"]
    assert b["lot"] == "1" and b["actual_cost"] == 2375309.26
    assert b["planned_cost"] == 1952120.53 and b["planned_days"] == 46 and b["actual_days"] == 46
    by_id = {d["id"]: d for d in p["documents"]}
    for field, sources in b["field_sources"].items():
        for evidence in sources if isinstance(sources, list) else [sources]:
            assert evidence["excerpt"] and evidence["excerpt"] in by_id[evidence["id"]]["text"]
            assert evidence["locator"].startswith("BZP, pole")
    assert p == dry
    assert project_view({**p, "scope": "część 2"})["contract_benchmarks"] == []


def test_contradictory_periods_zagrodno_compare_against_original_award(official_records):
    record = next(c for c in official_records if c["project"]["project_id"] == "RM-2026-002")
    view = project_view(reviewed(record))
    (b,) = view["contract_benchmarks"]
    assert b["planned_days"] == 61 and b["actual_days"] == 88
    (conflict,) = [c for c in view["projection_conflicts"] if c["field"] == "agreed_period"]
    assert {v["days"] for v in conflict["variants"]} == {61, 92}
    assert len({v["source"]["id"] for v in conflict["variants"]}) == 2
    assert b["period_evidence"]["original"]["source"]["locator"].endswith("8.3")


def test_desk_shows_original_period_and_field_for_each_pending_notice(official_records):
    record = next(c for c in official_records if c["project"]["project_id"] == "RM-2026-002")
    p = {**reviewed(record), "contracts": []}
    for observation in p["observations"]:
        observation["status"] = "pending"
    conflict = next(c for c in detailed_view(p)["conflicts"] if c["field"] == "planned_days")
    assert {v["value"] for v in conflict["variants"]} == {61, 92}
    docs = {d["id"]: d for d in p["documents"]}
    for variant in conflict["variants"]:
        ref = variant["field_reference"]
        assert ref["locator"] == "BZP, pole 4.2"
        assert variant["source_period"] in ref["excerpt"]
        assert ref["excerpt"] in docs[variant["source_id"]]["text"]
        assert ref["title"] == variant["source"]
        assert variant["status"] == "pending"
    docs[conflict["variants"][0]["source_id"]]["status"] = "rejected"
    assert all(c["field"] != "planned_days" for c in detailed_view(p)["conflicts"])


def test_blind_projection_uses_publication_and_separate_pre_award_snapshot(official_records):
    p = reviewed(official_records[0])
    assert p["observations"][-1]["facts"]["finished_on"] == "2023-06-22"
    early = project_view(p, as_of="2025-12-31")
    assert early["contract_benchmarks"] == []
    assert early["plan_snapshot"]["published_at"].startswith("2022-02-16")
    assert "planned_cost" not in early["plan_snapshot"]
    p["title"] = "ZMIENIONY_TYTUŁ_PO_AWARYJNYM_ODBIORZE"
    date = early["planned_at"]
    plan = project_view(p, as_of=date)["plan_snapshot"]
    assert p["title"] not in plan["title"] and p["title"] not in plan["description"]
    assert project_view(p, as_of="2026-03-10")["contract_benchmarks"]
    p["observations"][0]["corrected_at"] = "2026-05-01"
    assert "plan_snapshot" not in project_view(p, as_of=date)


def test_pending_link_rejected_document_and_conflicting_final_totals(official_records):
    p = reviewed(official_records[0])
    completion = next(r for r in p["observations"] if r["kind"] == "completion")
    completion["status"] = "pending"
    assert project_view(p)["contract_benchmarks"] == []
    completion["status"] = "accepted"
    d = next(d for d in p["documents"] if d["id"] == completion["source_id"])
    d["status"] = "rejected"
    assert project_view(p)["contract_benchmarks"] == []
    d["status"] = "accepted"
    alt = dict(d, id="different-notice")
    p["documents"].append(alt)
    p["observations"].append(
        {
            **completion,
            "id": "conflict",
            "source_id": alt["id"],
            "facts": {**completion["facts"], "paid_pln": 442000.00},
        }
    )
    result = project_view(p)
    assert result["contract_benchmarks"] == []
    assert result["projection_conflicts"][0]["field"] == "paid_pln"


def test_real_replay_sender_and_filtered_evidence_are_historical(official_records):
    cases = [reviewed(c) for c in official_records]
    target = next(c for c in cases if c["id"] == "RM-2026-018")
    cutoff = project_view(target)["planned_at"]
    res = run_backtest(target, cases, cutoff)
    assert res["metrics"]["actual_days"]["count"] >= 3
    assert res["metrics"]["cost_change_pct"]["scope"] == "contract"
    for p in res["metrics"]["cost_change_pct"]["points"]:
        assert p["id"] != target["id"]
        assert all(s["published_at"][:10] <= cutoff and "BZP, pole" in s["locator"] for s in p["sources"])
    # Choosing the full-investment scope must never pool contract amounts.
    plan = {
        "title": "Kanalizacja sanitarna",
        "description": "Budowa kanalizacji sanitarnej.",
        "metric_scope": "project",
    }
    assert analyze_project(plan, cases)["metrics"]["actual_days"]["count"] == 0
