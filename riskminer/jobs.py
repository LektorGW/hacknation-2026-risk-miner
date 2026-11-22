"""Small, transactionally leased enrichment queue for a single-node installation."""

import json
import logging
import os
import time
import uuid

from . import db

log = logging.getLogger("riskminer.jobs")


def enqueue(conn, pids, actor):
    jid = uuid.uuid4().hex
    conn.execute("INSERT INTO jobs VALUES(?,?,?)", (jid, db.timestamp(), actor))
    conn.executemany(
        "INSERT INTO tasks(job_id,project_id) VALUES(?,?)", [(jid, pid) for pid in dict.fromkeys(pids)]
    )
    return jid


def snapshot(conn, jid, full=True):
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not job:
        raise KeyError("Nie znaleziono zadania.")
    result = dict(job)
    items = [
        dict(project_id=r[0], status=r[1], **json.loads(r[2] or "{}"))
        for r in conn.execute(
            "SELECT project_id,status,result FROM tasks WHERE job_id=? ORDER BY project_id", (jid,)
        )
    ]
    statuses = [i["status"] for i in items]
    finished = sum(s in {"done", "partial", "failed"} for s in statuses)
    if finished < len(items):
        status = "queued" if statuses.count("queued") == len(items) else "running"
    elif all(s == "failed" for s in statuses):
        status = "failed"
    else:
        status = "done" if all(s == "done" for s in statuses) else "partial"
    result.update(status=status, total=len(items), finished=finished)
    if full:
        result["items"] = items
    return result


def claim():
    now = time.time()
    with db.connection(True) as c:
        c.execute(
            "UPDATE tasks SET status='failed',result=? WHERE status='running' AND lease<? AND attempt>=3",
            (db.dump({"error": "Przetwarzanie przerwane po trzech próbach."}), now),
        )
        task = c.execute(
            """SELECT job_id,project_id,attempt,actor FROM tasks JOIN jobs ON jobs.id=tasks.job_id
            WHERE status='queued' OR (status='running' AND lease<?) ORDER BY created_at,project_id LIMIT 1""",
            (now,),
        ).fetchone()
        if task:
            c.execute(
                "UPDATE tasks SET status='running',lease=?,attempt=attempt+1 WHERE job_id=? AND project_id=?",
                (now + 1800, task[0], task[1]),
            )
            return tuple(task)
    return None


def cycle():
    from .service import enrich_one

    t = claim()
    if not t:
        return False
    jid, pid, attempt, actor = t
    try:
        result = enrich_one(pid, actor)
        result.pop("project_id", None)
        status = "done" if result.get("complete", not result.get("warnings")) else "partial"
    except Exception:
        log.exception("Nieudane wzbogacenie projektu %s", pid)
        result = {"error": "Źródło lub proces przetwarzania jest niedostępny."}
        status = "queued" if attempt < 2 else "failed"
    with db.connection(True) as c:
        c.execute(
            "UPDATE tasks SET status=?,result=?,lease=0 WHERE job_id=? AND project_id=? AND attempt=?",
            (status, db.dump(result), jid, pid, attempt + 1),
        )
    return True


def schedule_active():
    interval = int(os.getenv("RISKMINER_MONITOR_HOURS", "6"))
    if interval <= 0:
        return
    with db.connection(True) as c:
        row = c.execute("SELECT body FROM settings WHERE id='last_monitor'").fetchone()
        if row and time.time() - float(row[0]) < interval * 3600:
            return
        ids = [
            r[0]
            for r in c.execute("""SELECT id FROM projects WHERE json_extract(body,'$.status')='active'
                AND NOT EXISTS(SELECT 1 FROM tasks WHERE tasks.project_id=projects.id AND status IN ('running','queued'))""")
        ]
        if ids:
            enqueue(c, ids, "monitor")
        c.execute("INSERT OR REPLACE INTO settings VALUES('last_monitor',?)", (str(time.time()),))


def worker(stop):
    next_monitor = 0
    while not stop.is_set():
        try:
            if time.monotonic() >= next_monitor:
                schedule_active()
                next_monitor = time.monotonic() + 60
            if cycle():
                continue
        except Exception:
            log.exception("Błąd przetwarzania kolejki, ponowienie za chwilę.")
        stop.wait(2)
