from riskminer import db, jobs


def test_retry_allows_other_projects_to_run_and_survives_worker_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("RISKMINER_DB", str(tmp_path / "registry.sqlite3"))
    db.initialize()
    with db.connection(True) as conn:
        for pid in ("A", "B"):
            db.put_project(conn, {"id": pid})
        jid = jobs.enqueue(conn, ["A", "B"], "operator")

    now = 1000
    calls = []

    def fetch(pid, actor):
        calls.append(pid)
        if calls == ["A"]:
            raise TimeoutError("temporary failure")
        return {"found": 1, "added": 1, "warnings": [], "complete": True}

    monkeypatch.setattr("riskminer.jobs.time.time", lambda: now)
    monkeypatch.setattr("riskminer.service.enrich_one", fetch)
    assert jobs.cycle()
    assert jobs.cycle()
    assert not jobs.cycle()
    assert calls == ["A", "B"]
    with db.connection() as conn:
        assert jobs.snapshot(conn, jid)["finished"] == 1
    now += 30
    assert jobs.cycle()
    with db.connection() as conn:
        assert jobs.snapshot(conn, jid)["status"] == "done"
    assert calls == ["A", "B", "A"]
