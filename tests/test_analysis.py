import copy
import json

import pytest

from riskminer.analysis import (
    _sensitivity,
    analyze_project,
    default_catalog,
    expert_materials,
    extract_events,
    extract_with_provider,
    infer_subsectors,
    run_backtest,
    subsectors,
)


def test_leave_one_project_out_preserves_ties_and_minimum_sample():
    points = [{"id": str(i), "value": value} for i, value in enumerate([-15, -15, 12, 80])]
    trials = _sensitivity(points, 200, "duration")
    assert trials[0] == {"omitted_id": "3", "count": 3, "low": 185, "high": 212}
    assert all(v["low"] == 185 for v in trials)
    assert all(v["high"] == 280 for v in trials[1:])
    cost = _sensitivity(points, 1_000_000, "cost")
    assert (cost[0]["low"], cost[0]["high"]) == (850000, 1120000)
    assert all(v["low"] is None and v["high"] is None and v["count"] == 2
               for v in _sensitivity(points[:3], 365, "duration"))


def doc(identifier, text, published, kind):
    return {
        "id": identifier,
        "title": identifier,
        "text": text,
        "published_at": published,
        "kind": kind,
        "url": "/api/files/" + identifier,
        "locator": "strona 1",
    }


def case(identifier, finish="2022-01-15", reported="2022-01-20", live=True):
    plan, outcome = identifier + "-plan", identifier + "-out"
    scope = "Modernizacja czynnej oczyszczalni ścieków, utrzymanie ciągłości pracy."
    return {
        "id": identifier,
        "title": scope,
        "description": scope,
        "type": "Oczyszczalnia ścieków",
        "status": "completed",
        "live_operation": live,
        "planned_at": "2020-05-01",
        "completed_at": finish,
        "plan_source_id": plan,
        "outcome_source_id": outcome,
        "field_sources": {"live_operation": plan, "type": plan, "planned_days": plan, "planned_cost": plan},
        "documents": [
            doc(plan, scope, "2020-05-01", "plan"),
            doc(outcome, "Podczas przełączenia wystąpiła awaria.", reported, "completion"),
        ],
        "events": [
            {
                "id": identifier + "-event",
                "category": "R05",
                "kind": "candidate_event",
                "title": "Awaria przy przełączeniu",
                "source_id": outcome,
                "status": "accepted",
            }
        ],
        "cost_basis": "PLN brutto",
        "planned_cost": 1000,
        "actual_cost": 1250,
        "planned_days": 100,
        "actual_days": 115,
    }


def test_blind_replay_removes_target_duplicates_outcome_and_late_publications():
    target = case("target", "2024-06-01", "2024-06-10")
    target["cst"] = "EU.01"
    target["description"] = "TAJNA_AWARIA z dokumentu końcowego"
    target["documents"][1]["text"] = target["description"]
    late = case("late-publication", reported="2024-10-10")
    future = case("future-project", finish="2025-01-01")
    duplicate = {**case("duplicate"), "cst": "EU.01"}
    valid = case("previous")
    undated = case("undated", reported=None)
    cases = [target, late, future, duplicate, valid, undated]
    input_backup = copy.deepcopy(cases)
    result = run_backtest(target, cases, "2023-01-01")
    assert result["replay"] == {"cutoff": "2023-01-01", "revealed": False}
    assert [c["id"] for c in result["comparables"]] == ["previous"]
    assert "TAJNA_AWARIA" not in json.dumps(result, ensure_ascii=False)
    assert result["metrics"]["cost_change_pct"]["points"][0]["value"] == 25
    reveal = run_backtest(target, cases, "2023-01-01", reveal=True)
    assert reveal["flags"] == result["flags"]
    assert reveal["replay"]["hits"] == ["R05"]
    assert reveal["replay"]["metrics"]["days_change"] == 15
    assert cases == input_backup


def test_undated_target_has_no_plan_and_no_future_evidence():
    target = case("x")
    target["documents"][0]["published_at"] = None
    result = run_backtest(target, [case("other")], "2020-01-01")
    assert result["sample_size"] == 0
    assert not result["flags"]
    assert result["schedule"]["planned_days"] is None
    assert any("datowanego" in warning for warning in result["warnings"])
    with pytest.raises(ValueError):
        run_backtest(target, [], "bez daty")


def test_reviewed_evidence_only_and_consistent_financial_basis():
    target = case("x")
    other = case("y")
    other.update(planned_cost_tax_basis="netto", actual_cost_tax_basis="brutto")
    other["events"].extend(
        [
            {**other["events"][0], "id": "excluded", "category": "R12", "status": "pending"},
            {**other["events"][0], "id": "no-proof", "category": "R13", "source_id": "missing"},
            {**other["events"][0], "id": "signal", "kind": "signal"},
        ]
    )
    res = analyze_project(target, [other])
    assert res["metrics"]["cost_change_pct"]["count"] == 0
    assert res["metrics"]["actual_days"]["count"] == 1
    assert [e["id"] for e in res["comparables"][0]["events"]] == ["y-event"]
    assert len(res["metrics"]["days_change"]["points"][0]["sources"]) == 2
    other["documents"][1]["status"] = "pending"
    assert analyze_project(target, [other])["metrics"]["actual_days"]["count"] == 0


def test_three_questions_and_partial_reconciliation_on_annex():
    base = {
        "title": "Modernizacja czynnej oczyszczalni",
        "description": "Utrzymanie ciągłości pracy obiektu.",
    }

    def continuity(p):
        return next(f for f in analyze_project(p, [], default_catalog())["flags"] if f["category"] == "R05")

    assert continuity(base)["status"] == "open"
    annex = {
        "title": "Załącznik",
        "text": "Kolejność przełączeń obejmuje dwa etapy.",
        "source": {"name": "SWZ.docx", "locator": "akapit 8"},
    }
    partial = continuity({**base, "documents": [annex]})
    assert partial["status"] == "partial" and len(partial["missing"]) == 1
    assert partial["answer_evidence"][0]["locator"] == "akapit 8"
    assert partial["answer_evidence"][0]["excerpt"] == annex["text"]
    annex["text"] += " Za przełączenia odpowiada operator."
    resolved = continuity({**base, "documents": [annex]})
    assert resolved["status"] == "documented" and resolved["review_status"] == "pending"
    annex["text"] = "Nie wskazano, kto za przełączenia odpowiada."
    assert continuity({**base, "documents": [annex]})["status"] == "open"


def test_extraction_exact_source_and_no_attributed_undocumented_impact():
    text = (
        "Nie stwierdzono kolizji. W razie kolizji termin może ulec zmianie. "
        "Z powodu kolizji przedłużono termin o 17 dni. "
        "Zmiana wynagrodzenia jest możliwa w przypadku dodatkowych robót."
    )
    document = doc("d", text, "2021-02-03", "change")
    events = extract_events(document)
    selected = [e for e in events if e["category"] == "R03"]
    assert {e["kind"] for e in selected} == {"signal", "candidate_event"}
    assert all("Nie stwierdzono" not in e["excerpt"] for e in events)
    for e in events:
        ref = e["evidence"][0]
        assert ref["excerpt"] == text[ref["start"] : ref["end"]]
        assert e["status"] == "pending"
        assert e["impact_cost_pln"] is None
    occurred = next(e for e in selected if e["kind"] == "candidate_event")
    assert occurred["impact_days"] == 17
    assert occurred["cause_excerpt"] == occurred["excerpt"]
    assert next(e for e in selected if e["kind"] == "signal")["impact_days"] is None


def test_editable_catalog_and_source_materials():
    mats = {k["id"]: k for k in expert_materials()}
    assert len(subsectors()) == 6
    assert infer_subsectors("Rozbudowa kanalizacji sanitarnej") == ["Kanalizacja sanitarna"]
    rules = default_catalog()
    assert [r["id"] for r in rules] == [f"R{i:02}" for i in range(1, 16)]
    for r in rules:
        assert mats[r["expert_source"]["id"]]["excerpt"].startswith(r["id"])
    custom = [{"id": "X7", "title": "Pilotaż", "terms": ["pilotaż"]}]
    found = extract_events(doc("doc", "Opisuje pilotaż.", "2024-01-01", "notice"), custom)
    assert [e["category"] for e in found] == ["X7"]
    assert extract_events(doc("doc", "Opisuje pilotaż.", "2024-01-01", "notice"), []) == []
    result = analyze_project(
        {"title": "Rozbudowa sieci wodociągowej", "description": "Brak dostępu do sieci."}, []
    )
    assert len(result["water_supply_checklist"]) == 9
    assert result["water_supply_checklist"][0]["evidence"]


def test_operational_filter_range_and_small_sample():
    new = {"title": "Oczyszczalnia", "type": "Oczyszczalnia ścieków", "planned_days": 80}
    cases = [case("a"), case("b"), case("c", live=False)]
    all_cases = analyze_project(new, cases)
    assert all_cases["schedule"]["assessment"] == "below_range"
    filtered = analyze_project(new, cases, filters={"live_operation": True})
    assert filtered["sample_size"] == 2 and filtered["schedule"]["assessment"] == "insufficient"
    assert len(filtered["metrics"]["actual_days"]["points"]) == 2


def test_registry_only_confirms_similarity_and_pending_links_cannot_confirm_results():
    other = case("registry-entry")
    other["documents"] = [
        doc("sheet", "Wiersz z nazwą inwestycji", "2023-06-02", "registry"),
        {**other["documents"][1], "status": "pending"},
    ]
    other["registry_source_id"] = "sheet"
    # The stale citation in the event and metric claims 'accepted', but the
    # current linked source in storage is pending.
    stale = {**other["documents"][1], "status": "accepted"}
    other["field_sources"]["actual_cost"] = stale
    other["events"][0].pop("source_id")
    other["events"][0]["evidence"] = [stale]
    result = analyze_project(case("target"), [other])
    assert result["sample_size"] == 1
    assert [r["id"] for r in result["comparables"][0]["evidence"]] == ["sheet"]
    assert result["metrics"]["cost_change_pct"]["count"] == 0
    assert result["comparables"][0]["events"] == []
    assert run_backtest(case("target"), [other], "2023-01-01")["sample_size"] == 0


def test_replay_omits_later_expert_decision_or_edit_even_if_source_is_old():
    other = case("other")
    other["events"][0]["reviewed_at"] = "2025-05-01T12:00:00Z"
    other["actual_cost"] = 9000
    other["live_operation"] = True
    other["field_updated_at"] = {"actual_cost": "2025-03-01", "live_operation": "2024-04-03"}
    result = run_backtest(case("target"), [other], "2023-01-01")
    assert result["comparables"][0]["events"] == []
    assert result["comparables"][0]["live_operation"] is None
    assert result["metrics"]["cost_change_pct"]["count"] == 0
    assert analyze_project(case("target"), [other])["metrics"]["cost_change_pct"]["max"] == 800


def test_model_is_optional_and_drops_hallucinated_evidence(monkeypatch):
    from riskminer import model_provider

    document = doc("d", "Wystąpiło zdarzenie lokalne.", "2022-01-01", "change")
    rules = [{"id": "X", "title": "Nowa kategoria", "terms": ["inny sygnał"]}]
    monkeypatch.setenv("RISKMINER_MODEL_PROVIDER", "rules")
    assert extract_with_provider(document, rules) == []
    monkeypatch.setenv("RISKMINER_MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("RISKMINER_MODEL_URL", "http://127.0.0.1:11434/v1/chat/completions")
    monkeypatch.setenv("RISKMINER_MODEL", "test")
    monkeypatch.setattr(
        model_provider,
        "_model_json",
        lambda *_: [
            {"category": "X", "kind": "candidate_event", "excerpt": "Zmyślone zdanie."},
            {"category": "X", "kind": "candidate_event", "excerpt": "zdarzenie lokalne."},
            {"category": "X", "kind": "candidate_event", "excerpt": document["text"]},
        ],
    )
    res = extract_with_provider(document, rules)
    assert len(res) == 1 and res[0]["excerpt"] == document["text"] and res[0]["status"] == "pending"
