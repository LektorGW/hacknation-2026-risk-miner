"""SQLite storage with atomic imports, entity relationships and an append-only review trail."""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GROUPS = ("documents", "events", "observations", "procedures", "contracts", "changes", "measurements")


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))


def key(prefix, *parts):
    return prefix + "-" + hashlib.sha256(dump(parts).encode()).hexdigest()[:24]


def path():
    return Path(os.environ.get("RISKMINER_DB", ROOT / "var" / "riskminer.sqlite3"))


@contextmanager
def connection(write=False):
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize():
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, name TEXT NOT NULL, data BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS entities(
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            kind TEXT NOT NULL, source_id TEXT REFERENCES entities(id),
            contract_id TEXT REFERENCES entities(id), procedure_id TEXT REFERENCES entities(id),
            body TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS entity_project ON entities(project_id,kind);
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            entity_id TEXT NOT NULL REFERENCES entities(id), status TEXT NOT NULL, body TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS review_queue ON reviews(status,project_id);
        CREATE TABLE IF NOT EXISTS settings(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS replays(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS category_proposals(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,actor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(job_id TEXT NOT NULL REFERENCES jobs(id),project_id TEXT NOT NULL REFERENCES projects(id),
            status TEXT NOT NULL DEFAULT 'queued',attempt INTEGER NOT NULL DEFAULT 0,lease REAL NOT NULL DEFAULT 0,result TEXT,
            PRIMARY KEY(job_id,project_id));
        CREATE INDEX IF NOT EXISTS task_ready ON tasks(status,lease);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, at TEXT NOT NULL,
            actor TEXT NOT NULL, action TEXT NOT NULL, subject TEXT, body TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS audit_keep BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'immutable'); END;
        CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'immutable'); END;
        """)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS revision(id INTEGER PRIMARY KEY, database_id TEXT NOT NULL, generation INTEGER NOT NULL)"
        )
        conn.execute("INSERT OR IGNORE INTO revision VALUES(1, hex(randomblob(16)), 0)")
        for table in (
            "projects",
            "entities",
            "reviews",
            "audit",
            "settings",
            "jobs",
            "tasks",
            "category_proposals",
        ):
            for operation in ("INSERT", "UPDATE", "DELETE"):
                conn.execute(f"""CREATE TRIGGER IF NOT EXISTS revision_{table}_{operation}
                    AFTER {operation} ON {table} BEGIN UPDATE revision SET generation=generation+1 WHERE id=1; END""")
        conn.commit()
    finally:
        conn.close()


def audit(conn, actor, action, subject, **detail):
    conn.execute(
        "INSERT INTO audit(at,actor,action,subject,body) VALUES(?,?,?,?,?)",
        (timestamp(), actor, action, subject, dump(detail)),
    )


def history(conn, limit=100):
    return [
        dict(
            id=r["seq"],
            created_at=r["at"],
            at=r["at"],
            actor=r["actor"],
            action=r["action"],
            subject=r["subject"],
            detail=json.loads(r["body"]),
        )
        for r in conn.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT ?", (limit,))
    ]


def put_project(conn, obj):
    conn.execute(
        "INSERT INTO projects VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
        (obj["id"], dump({k: v for k, v in obj.items() if k not in GROUPS})),
    )


def entity(conn, eid):
    row = conn.execute("SELECT body FROM entities WHERE id=?", (eid,)).fetchone()
    return json.loads(row[0]) if row else None


def put_entity(conn, pid, kind, obj):
    if kind not in GROUPS:
        raise ValueError("Nieznany typ rekordu.")
    obj = {**obj, "project_id": pid}
    for field, expected in (
        ("contract_id", "contracts"),
        ("procedure_id", "procedures"),
        ("source_id", "documents"),
    ):
        if obj.get(field):
            found = conn.execute(
                "SELECT project_id,kind FROM entities WHERE id=?", (obj[field],)
            ).fetchone()
            if not found or tuple(found) != (pid, expected):
                raise ValueError("Wskazany rekord nie należy do tej inwestycji lub ma niewłaściwy typ.")
    conn.execute(
        """INSERT INTO entities VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        source_id=excluded.source_id, contract_id=excluded.contract_id, procedure_id=excluded.procedure_id,
        body=excluded.body WHERE entities.kind=excluded.kind AND entities.project_id=excluded.project_id""",
        (
            obj["id"],
            pid,
            kind,
            obj.get("source_id"),
            obj.get("contract_id"),
            obj.get("procedure_id"),
            dump(obj),
        ),
    )


def projects(conn, pid=None):
    params = (pid,) if pid else ()
    items = {}
    for row in conn.execute(
        "SELECT body FROM projects" + (" WHERE id=?" if pid else "") + " ORDER BY id", params
    ):
        obj = json.loads(row[0])
        items[obj["id"]] = {**obj, **{k: [] for k in GROUPS}}
    for r in conn.execute(
        "SELECT project_id,kind,body FROM entities"
        + (" WHERE project_id=?" if pid else "")
        + " ORDER BY rowid",
        params,
    ):
        items[r[0]][r[1]].append(json.loads(r[2]))
    return list(items.values())


def project(conn, pid):
    found = projects(conn, pid)
    if not found:
        raise KeyError("Nie znaleziono projektu.")
    return found[0]


def catalog(conn):
    from .analysis import default_catalog

    row = conn.execute("SELECT body FROM settings WHERE id='catalog'").fetchone()
    return json.loads(row[0]) if row else default_catalog()


def sectors(conn):
    from .sectors import default_sectors

    row = conn.execute("SELECT body FROM settings WHERE id='sectors'").fetchone()
    return json.loads(row[0]) if row else default_sectors()


def enqueue(conn, pid, kind, obj):
    rid = key("review", obj["id"])
    review = dict(
        id=rid,
        project_id=pid,
        entity_id=obj["id"],
        kind=kind,
        title=obj.get("title", ""),
        status="pending",
        payload=obj,
        source_id=obj.get("source_id"),
        updated_at=timestamp(),
        version=1,
    )
    conn.execute(
        "INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?)", (rid, pid, obj["id"], "pending", dump(review))
    )


def reviews(conn):
    return [
        json.loads(r[0])
        for r in conn.execute("SELECT body FROM reviews ORDER BY (status='pending') DESC,rowid DESC")
    ]
