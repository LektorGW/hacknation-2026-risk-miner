import json

from riskminer.benchmark import build_cases, select_rows


def test_blank_identifiers_do_not_select_or_attach_unrelated_notices():
    project = {"title": "Remont sieci"}
    other = {"noticeNumber": "2025/BZP 00000015/01", "noticeType": "ContractNotice", "orderObject": "Remont sieci"}
    assert select_rows([project], [json.dumps(other)]) == []
    assert build_cases([project], [other, {"noticeType": "ContractNotice"}], "2026-01-01")[0]["records"] == []


def test_normalized_notice_without_procedure_stays_a_single_notice():
    project = {"title": "Remont sieci", "bzp": "2025 / BZP 15/02"}
    record = {"orderObject": project["title"], "noticeType": "ContractNotice"}
    records = [{**record, "bzpNumber": f"2025/BZP {number}"} for number in ("00000015/01", "00000015/02", "00000016/01")]
    selected = select_rows([project], map(json.dumps, records))
    assert selected == records[:2]
    assert [r["external_id"] for r in build_cases([project], records, "2026-01-01")[0]["records"]] == ["2025/BZP 00000015/02"]
