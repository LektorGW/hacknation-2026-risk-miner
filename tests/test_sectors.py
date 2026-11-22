import pytest

from riskminer.analysis import analyze_project, default_catalog
from riskminer.sectors import adapt, default_sectors, rules_for_sector, validate_sectors


def modules():
    rail = {
        "id": "rail",
        "name": "Transport kolejowy",
        "description": "Pilotaż kolejowy.",
        "aliases": ["kolej"],
        "types": [{"name": "Stacja pasażerska", "terms": ["peron", "stacja"]}],
    }
    return validate_sectors([*default_sectors(), rail])


def test_second_sector_uses_its_rules_types_and_only_same_sector_comparables():
    sectors = modules()
    rules = [
        *default_catalog(),
        {
            "id": "K01",
            "title": "Dostępność peronu",
            "sector_ids": ["rail"],
            "signals": ["peron"],
            "question": "Gdzie przewidziano dojście do peronu?",
        },
    ]
    base = {
        "id": "new",
        "sector": "kolej",
        "title": "Budowa peronu",
        "description": "Włączenie odwodnienia do sieci wodociągowej.",
    }
    source = {"id": "reg", "title": "Rejestr", "locator": "wiersz 1", "text": "Stacja z peronem."}
    old = {
        "id": "old",
        "sector": "Transport kolejowy",
        "title": "Stacja z peronem",
        "status": "completed",
        "registry_source_id": "reg",
        "documents": [source],
    }
    water = {**old, "id": "w", "sector": "Gospodarka wodno-ściekowa"}
    p, group, selected = adapt(base, [old, water], rules, sectors)
    result = analyze_project(p, group, selected)
    assert result["sector"]["type"] == "Stacja pasażerska"
    assert [c["id"] for c in result["comparables"]] == ["old"]
    assert [r["category"] for r in result["flags"]] == ["K01"]
    assert result["water_supply_checklist"] == []
    assert [r["id"] for r in rules_for_sector(old, rules, sectors)] == ["K01"]
    assert len(rules_for_sector(water, rules, sectors)) == 15


def test_replay_module_selection_is_grounded_in_historical_planning_snapshot():
    modules_ = modules()
    p = {
        "id": "t",
        "sector": "Gospodarka wodno-ściekowa",
        "title": "Późniejsza wzmianka o sieci wodociągowej",
        "documents": [
            {
                "id": "swz",
                "kind": "plan",
                "title": "Modernizacja peronu",
                "text": "Stacja pasażerska. Wydłużenie peronu.",
                "published_at": "2020-06-01",
                "status": "accepted",
            }
        ],
    }
    other = {
        **p,
        "id": "c",
        "sector": "kolej",
        "documents": [{**p["documents"][0], "published_at": "2026-01-01"}],
    }
    target, group, rules = adapt(p, [other], default_catalog(), modules_, as_of="2020-07-01")
    assert target["_sector_module"]["id"] == "rail" and group == [] and rules == []
    undated, _, _ = adapt(other, [], default_catalog(), modules_, as_of="2020-07-01")
    assert undated["_sector_module"] is None


def test_unresolved_sector_does_not_use_water_catalog_and_alias_collisions_fail():
    sectors = modules()
    target, cases, rules = adapt({"sector": "Energetyka", "title": "Węzeł"}, [], default_catalog(), sectors)
    result = analyze_project(target, cases, rules)
    assert not result["flags"]
    assert any("sektora" in w for w in result["warnings"])
    sectors[1]["aliases"].append("wod-kan")
    with pytest.raises(ValueError):
        validate_sectors(sectors)
