"""HTTP application for the registry, evidence desk and planning workspace."""

import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware

from . import analysis, db, jobs, workflow
from .preview import mark_provisional, preview_cases
from .case_view import detailed_view


MAX_UPLOAD = 16 * 1024 * 1024
ROLES = {"viewer": 0, "expert": 1, "admin": 2}
PROJECT_FIELDS = set(
    "title description buyer location sector type status planned_cost actual_cost planned_days actual_days start_date end_date completed_at planned_at live_operation plan_source_id outcome_source_id field_sources exemplary".split()
)
EDIT_FIELDS = set(
    "title description category excerpt contract_id procedure_id comment exemplary reason cause impact mitigation confidence published_at kind value unit fact_type".split()
)
PROJECT_FIELDS.update({"sector_id", "currency", "cost_basis", "metric_scope"})
_remote_slots = threading.BoundedSemaphore(3)
_state_lock = threading.Lock()
_state_cache = (None, b"")


def accounts():
    raw = os.getenv("RISKMINER_ACCOUNTS", "{}")
    accts = json.loads(raw)
    if not isinstance(accts, dict):
        raise ValueError("Konfiguracja kont musi być obiektem JSON.")
    for name, acct in accts.items():
        if (
            not name
            or acct.get("role") not in ROLES
            or not re.fullmatch(r"[0-9a-f]{64}", acct.get("sha256", ""))
        ):
            raise ValueError("Niepoprawna konfiguracja kont.")
    if os.getenv("RISKMINER_ENV") == "production" and not any(a["role"] == "admin" for a in accts.values()):
        raise RuntimeError("Tryb produkcyjny wymaga skonfigurowania konta administratora.")
    return accts


def identity(request: Request):
    accts = request.app.state.accounts
    if not accts:
        if request.client and request.client.host in {"127.0.0.1", "::1", "testclient"}:
            return {"actor": "lokalny-ekspert", "role": "admin", "required": False}
        raise HTTPException(403, "Dostęp bez uwierzytelnienia jest dostępny tylko lokalnie.")
    token = request.headers.get("authorization", "")
    if token.startswith("Bearer "):
        digest = hashlib.sha256(token[7:].encode()).hexdigest()
        for name, a in accts.items():
            if hmac.compare_digest(digest, a["sha256"]):
                return {"actor": name, "role": a["role"], "required": True}
    raise HTTPException(401, "Podaj token dostępu do Risk Minera.", headers={"WWW-Authenticate": "Bearer"})


def role(minimum):
    def check(user=Depends(identity)):
        if ROLES[user["role"]] < ROLES[minimum]:
            raise HTTPException(403, "To działanie wymaga wyższych uprawnień.")
        return user

    return check


@asynccontextmanager
async def lifecycle(app):
    app.state.accounts = accounts()
    db.initialize()
    stop = threading.Event()
    runner = threading.Thread(target=jobs.worker, args=(stop,), daemon=True, name="riskminer-enrichment")
    enabled = os.getenv("RISKMINER_WORKER", "1") != "0"
    if enabled:
        runner.start()
    try:
        yield
    finally:
        stop.set()
        if enabled:
            runner.join(timeout=2)


app = FastAPI(
    title="Risk Miner", version="1.0.0", lifespan=lifecycle, docs_url=None, redoc_url=None, openapi_url=None
)
hosts = os.getenv("RISKMINER_HOSTS", "127.0.0.1,localhost,[::1],testserver").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[s.strip() for s in hosts])
app.add_middleware(GZipMiddleware, minimum_size=2400, compresslevel=4)


@app.middleware("http")
async def bounds(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower():
            return JSONResponse({"detail": "Żądanie pochodzi z innej domeny."}, 403)
        limit = MAX_UPLOAD + 65536 if request.url.path in ("/api/import", "/api/parse") else 2 * 1024 * 1024
        try:
            if int(request.headers.get("content-length", "0")) > limit:
                return JSONResponse({"detail": "Przekroczono limit rozmiaru żądania."}, 413)
        except ValueError:
            return JSONResponse({"detail": "Nieprawidłowy rozmiar żądania."}, 400)
        # Bound chunked bodies too, before the multipart parser allocates temporary storage.
        total = 0
        pieces = []
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                return JSONResponse({"detail": "Przekroczono limit rozmiaru żądania."}, 413)
            pieces.append(chunk)
        request._body = b"".join(pieces)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc)[:700]}, 422)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse({"detail": str(exc.args[0])}, 404)


@app.get("/healthz")
def health():
    with db.connection() as conn:
        conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(db.ROOT / "static" / "index.html")


def state_data(conn):
    projects = [detailed_view(p) for p in db.projects(conn)]
    reviews = db.reviews(conn)
    stats = dict(
        projects=len(projects),
        documents=sum(len(p["documents"]) for p in projects),
        pending=sum(r["status"] == "pending" for r in reviews),
        completed=sum(p.get("status") == "completed" for p in projects),
    )
    # Lists serve short previews; the project route carries full source text.
    for p in projects:
        for group in ("documents", "observations"):
            for record in p[group]:
                record["text"] = str(record.get("text", ""))[:700]
    for r in reviews:
        if "text" in r["payload"]:
            r["payload"]["text"] = str(r["payload"]["text"])[:700]
    recent = [
        jobs.snapshot(conn, r[0], False)
        for r in conn.execute("SELECT id FROM jobs ORDER BY created_at DESC LIMIT 10")
    ]
    suggestions = [
        json.loads(r[0]) for r in conn.execute("SELECT body FROM category_proposals ORDER BY rowid DESC")
    ]
    return dict(
        projects=projects,
        reviews=reviews,
        catalog=db.catalog(conn),
        audit=db.history(conn),
        jobs=recent,
        category_proposals=suggestions,
        sectors=db.sectors(conn),
        stats=stats,
        model=analysis.model_info(),
    )


@app.get("/api/state")
def state(user=Depends(identity)):
    global _state_cache
    with _state_lock, db.connection() as conn:
        version = tuple(conn.execute("SELECT database_id,generation FROM revision WHERE id=1").fetchone())
        if _state_cache[0] != version:
            _state_cache = (version, db.dump(state_data(conn)).encode("utf-8"))
        shared = _state_cache[1]
    # Permission metadata is per request; serialized catalogue and source previews are shared.
    content = b'{"auth":' + db.dump(user).encode("utf-8") + b"," + shared[1:]
    return Response(content, media_type="application/json")


@app.get("/api/projects/{pid}")
def detail(pid: str, user=Depends(identity)):
    with db.connection() as conn:
        return detailed_view(db.project(conn, pid))


@app.get("/api/files/{fid}")
def get_file(fid: str, user=Depends(identity)):
    with db.connection() as conn:
        row = conn.execute("SELECT name,data FROM files WHERE id=?", (fid,)).fetchone()
        if not row:
            raise KeyError("Nie znaleziono pliku.")
        return Response(
            row[1],
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(row[0], safe="")},
        )


@app.get("/api/knowledge")
def knowledge(user=Depends(identity)):
    return analysis.expert_materials()


@app.get("/api/sectors")
def sector_list(user=Depends(identity)):
    with db.connection() as conn:
        return {"sectors": db.sectors(conn)}


@app.put("/api/sectors")
def sector_config(body: dict = Body(...), user=Depends(role("admin"))):
    from .sectors import validate_sectors

    modules = validate_sectors(body.get("sectors"))
    with db.connection(True) as conn:
        previous = db.sectors(conn)
        db.audit(conn, user["actor"], "edit_sectors", "sectors", before=previous, after=modules)
        conn.execute("INSERT OR REPLACE INTO settings VALUES('sectors',?)", (db.dump(modules),))
    return {"sectors": modules}


@app.get("/api/knowledge/{kid}")
def knowledge_item(kid: str, user=Depends(identity)):
    for item in analysis.expert_materials():
        if item["id"] == kid:
            with db.connection() as conn:
                original = conn.execute("SELECT body FROM settings WHERE id='knowledge_files'").fetchone()
                fid = json.loads(original[0]).get(item["source"]) if original else None
            return {**item, "original_url": f"/api/files/{fid}" if fid else None}
    raise KeyError("Nie znaleziono fragmentu.")


def parsed(file):
    from .ingest import load_file

    name = Path((file.filename or "plik").replace("\\", "/")).name[:200]
    data = file.file.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("Prześlij niepusty plik do 16 MiB.")
    return name, data, load_file(name, data)


@app.post("/api/parse")
def parse(file: UploadFile = File(...), user=Depends(identity)):
    name, data, rows = parsed(file)
    return {"records": rows, "filename": name}


def enrich_one(pid, actor):
    from .sources import enrich

    if not _remote_slots.acquire(blocking=False):
        raise HTTPException(429, "Trwają inne pobrania. Spróbuj ponownie za chwilę.")
    try:
        with db.connection() as conn:
            p = db.project(conn, pid)
        result = enrich(p)
        with db.connection(True) as conn:
            added = workflow.add_observations(conn, pid, result["records"], actor)
        return dict(
            project_id=pid,
            found=len(result["records"]),
            added=added,
            warnings=result.get("warnings", []),
            source_status=result.get("source_status", {}),
            complete=result.get("complete", not result.get("warnings")),
        )
    finally:
        _remote_slots.release()


@app.post("/api/import")
def upload(
    file: UploadFile = File(...),
    project_id: str | None = Form(None),
    enrich: bool = Form(False),
    user=Depends(role("expert")),
):
    name, data, rows = parsed(file)
    with db.connection(True) as conn:
        ids = workflow.import_rows(conn, name, data, rows, user["actor"], project_id)
        jid = jobs.enqueue(conn, ids, user["actor"]) if enrich and len(ids) > 1 else None
    results = [enrich_one(ids[0], user["actor"])] if enrich and not jid else []
    return dict(
        project_ids=ids,
        projects=len(ids),
        records=len(rows),
        enrichment=results,
        job_id=jid,
        warnings=[w for res in results for w in res["warnings"]],
    )


@app.get("/api/jobs/{jid}")
def job_progress(jid: str, user=Depends(identity)):
    with db.connection() as conn:
        return jobs.snapshot(conn, jid)


@app.post("/api/projects/{pid}/enrich")
def enrich_api(pid: str, user=Depends(role("expert"))):
    return enrich_one(pid, user["actor"])


@app.patch("/api/projects/{pid}")
def edit_project(pid: str, body: dict = Body(...), user=Depends(role("expert"))):
    changes = body.get("fields", body)
    if not isinstance(changes, dict) or not set(changes) <= PROJECT_FIELDS:
        raise ValueError("Nieobsługiwane pola projektu.")
    if "status" in changes and changes["status"] not in {"completed", "active", "planned"}:
        raise ValueError("Nieprawidłowy status inwestycji.")
    if "title" in changes and not str(changes["title"] or "").strip():
        raise ValueError("Tytuł projektu jest wymagany.")
    with db.connection(True) as conn:
        p = db.project(conn, pid)
        for field in ("planned_cost", "actual_cost", "planned_days", "actual_days"):
            n = changes.get(field)
            if n is not None and (type(n) not in (int, float) or not math.isfinite(n) or n < 0):
                raise ValueError("Koszt i czas muszą być nieujemną liczbą.")
        refs = {**(changes.get("field_sources") or {})}
        for field in ("plan_source_id", "outcome_source_id"):
            if changes.get(field):
                refs[field] = changes[field]
        for ref in refs.values():
            if ref not in {d["id"] for d in p["documents"]}:
                raise ValueError("Dowód musi należeć do dokumentów projektu.")
        db.audit(
            conn, user["actor"], "edit_project", pid, before={k: p.get(k) for k in changes}, after=changes
        )
        p.update(changes)
        p["field_updated_at"] = {**p.get("field_updated_at", {}), **{k: db.timestamp() for k in changes}}
        db.put_project(conn, p)
        return p


@app.post("/api/reviews/{rid}")
def decide(rid: str, body: dict = Body(...), user=Depends(role("expert"))):
    decision = body.get("decision")
    patch = body.get("patch") or {}
    if (
        decision not in {"accepted", "corrected", "rejected"}
        or not isinstance(patch, dict)
        or not set(patch) <= EDIT_FIELDS
    ):
        raise ValueError("Nieprawidłowa decyzja lub zakres zmiany.")
    if decision == "corrected" and not patch:
        raise ValueError("Wprowadź poprawkę.")
    with db.connection(True) as conn:
        raw = conn.execute("SELECT body FROM reviews WHERE id=?", (rid,)).fetchone()
        if not raw:
            raise KeyError("Nie znaleziono pozycji do oceny.")
        r = json.loads(raw[0])
        if r["status"] == "superseded":
            raise HTTPException(409, "Ta propozycja ma nowszą wersję dokumentu.")
        if body.get("version", r["version"]) != r["version"] or (
            r["status"] != "pending" and "version" not in body
        ):
            raise HTTPException(409, "Decyzja już się zmieniła. Odśwież widok.")
        item = db.entity(conn, r["entity_id"])
        before = item.copy()
        item.update(patch)
        if "contract_id" in item and not item["contract_id"]:
            item["contract_id"] = None
        item["status"] = "rejected" if decision == "rejected" else "accepted"
        item["review_status"] = item["status"]
        item["reviewed_at"] = db.timestamp()
        if decision == "corrected":
            item["corrected_at"] = db.timestamp()
        if r["kind"] == "observations":
            evidence = db.entity(conn, item["source_id"])
            evidence["status"] = item["status"]
            evidence["review_status"] = item["status"]
            if decision == "corrected":
                evidence["corrected_at"] = item["corrected_at"]
            db.put_entity(conn, r["project_id"], "documents", evidence)
            if item["status"] == "accepted":
                workflow.materialize_notice(conn, r["project_id"], item)
                if "contract_id" in patch:
                    workflow.correct_contract(conn, r["project_id"], item, patch["contract_id"])
        db.put_entity(conn, r["project_id"], r["kind"], item)
        if r["kind"] == "observations":
            workflow.reconcile_relationships(conn, r["project_id"])
        r.update(
            status=decision,
            version=r["version"] + 1,
            payload=item,
            updated_at=db.timestamp(),
            actor=user["actor"],
            comment=str(body.get("comment") or "")[:3000],
        )
        conn.execute("UPDATE reviews SET status=?,body=? WHERE id=?", (decision, db.dump(r), rid))
        db.audit(
            conn,
            user["actor"],
            "review",
            rid,
            decision=decision,
            before=before,
            after=item,
            comment=r["comment"],
        )
        return r


@app.patch("/api/projects/{pid}/records/{eid}")
def annotate(pid: str, eid: str, body: dict = Body(...), user=Depends(role("expert"))):
    fields = body.get("fields")
    if not isinstance(fields, dict) or not fields or not set(fields) <= EDIT_FIELDS - {"excerpt"}:
        raise ValueError("Podaj obsługiwane pola korekty metadanych.")
    with db.connection(True) as conn:
        row = conn.execute(
            "SELECT kind,body FROM entities WHERE project_id=? AND id=?", (pid, eid)
        ).fetchone()
        if not row:
            raise KeyError("Nie znaleziono rekordu w projekcie.")
        before = json.loads(row[1])
        item = {**before, **fields, "edited_at": db.timestamp()}
        if row[0] == "observations" and "contract_id" in fields:
            workflow.correct_contract(conn, pid, item, fields["contract_id"])
            item["corrected_at"] = db.timestamp()
        for name in ("contract_id", "procedure_id"):
            if name in fields and not fields[name]:
                item[name] = None
        db.put_entity(conn, pid, row[0], item)
        if row[0] == "observations":
            workflow.reconcile_relationships(conn, pid)
        review = conn.execute("SELECT id,body FROM reviews WHERE entity_id=?", (eid,)).fetchone()
        if review:
            r = json.loads(review["body"])
            r.update(
                payload=item,
                title=item.get("title", ""),
                updated_at=db.timestamp(),
                version=r["version"] + 1,
            )
            conn.execute("UPDATE reviews SET body=? WHERE id=?", (db.dump(r), r["id"]))
        db.audit(
            conn,
            user["actor"],
            "annotate",
            eid,
            before={k: before.get(k) for k in fields},
            after=fields,
            comment=str(body.get("comment", ""))[:3000],
        )
        return item


@app.put("/api/catalog")
def save_catalog(body: dict = Body(...), user=Depends(role("admin"))):
    rules = body.get("rules")
    if (
        not isinstance(rules, list)
        or len(rules) > 300
        or any(
            not isinstance(r, dict)
            or not isinstance(r.get("id"), str)
            or not r["id"].strip()
            or not isinstance(r.get("title"), str)
            or not r["title"].strip()
            for r in rules
        )
        or len({r["id"] for r in rules}) != len(rules)
    ):
        raise ValueError("Każda reguła musi mieć unikatowy identyfikator i nazwę.")
    for r in rules:
        for field in ("signals", "aliases", "terms", "keywords"):
            if field in r and (
                not isinstance(r[field], list) or any(not isinstance(v, str) for v in r[field])
            ):
                raise ValueError("Sygnały i synonimy muszą być listą fraz.")
        if not isinstance(r.get("checks", []), list) or any(
            not isinstance(v, dict)
            or not isinstance(v.get("terms", []), list)
            or any(not isinstance(s, str) for s in v.get("terms", []))
            for v in r.get("checks", [])
        ):
            raise ValueError("Każdy warunek reguły wymaga listy fraz.")
        if r.get("expert_source") is not None and not isinstance(r["expert_source"], dict):
            raise ValueError("Źródło reguły wymaga opisu dokumentu.")
    with db.connection(True) as conn:
        previous = db.catalog(conn)
        db.audit(conn, user["actor"], "edit_catalog", "catalog", before=previous, after=rules)
        conn.execute("INSERT OR REPLACE INTO settings VALUES('catalog',?)", (db.dump(rules),))
    return {"rules": rules}


@app.post("/api/catalog/proposals")
def suggest_category(body: dict = Body(...), user=Depends(role("expert"))):
    title = body.get("title")
    terms = body.get("signals")
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(terms, list)
        or not terms
        or any(not isinstance(t, str) or not t.strip() for t in terms)
    ):
        raise ValueError("Nowa kategoria wymaga nazwy i przynajmniej jednej frazy źródłowej.")
    with db.connection(True) as conn:
        sid = body.get("source_id")
        if (
            sid
            and not conn.execute(
                "SELECT 1 FROM entities WHERE id=? AND kind='documents'", (sid,)
            ).fetchone()
        ):
            raise ValueError("Dokument źródłowy musi istnieć w rejestrze.")
        sectors = body.get("sector_ids") or ["water"]
        available = {m["id"] for m in db.sectors(conn)}
        if not isinstance(sectors, list) or any(
            not isinstance(s, str) or s not in available for s in sectors
        ):
            raise ValueError("Wybierz zarejestrowany sektor.")
        cid = db.key("kat", title.strip(), terms, sectors)
        r = dict(
            id=cid,
            title=title.strip(),
            signals=terms,
            question=str(body.get("question") or ""),
            reason=str(body.get("reason") or ""),
            source_id=sid,
            sector_ids=sectors,
            status="pending",
            author=user["actor"],
            at=db.timestamp(),
        )
        if not conn.execute(
            "INSERT OR IGNORE INTO category_proposals VALUES(?,?)", (cid, db.dump(r))
        ).rowcount:
            raise HTTPException(409, "Taka propozycja już istnieje.")
        db.audit(conn, user["actor"], "propose_category", cid, proposal=r)
        return r


@app.post("/api/catalog/proposals/{cid}")
def decide_category(cid: str, body: dict = Body(...), user=Depends(role("admin"))):
    decision = body.get("decision")
    if decision not in ("accepted", "rejected"):
        raise ValueError("Wybierz decyzję.")
    with db.connection(True) as conn:
        row = conn.execute("SELECT body FROM category_proposals WHERE id=?", (cid,)).fetchone()
        if not row:
            raise KeyError("Nie znaleziono propozycji.")
        r = json.loads(row[0])
        if r["status"] != "pending":
            raise HTTPException(409, "Propozycja została już oceniona.")
        if decision == "accepted":
            rules = db.catalog(conn)
            if any(workflow.fold(rule["title"]) == workflow.fold(r["title"]) for rule in rules):
                raise ValueError("Kategoria o tej nazwie figuruje już w katalogu.")
            rule = {k: r[k] for k in ("id", "title", "signals", "question")}
            rule["sector_ids"] = r.get("sector_ids") or ["water"]
            rule.update(enabled=True, action=r["reason"], checks=[])
            if r.get("source_id"):
                doc = db.entity(conn, r["source_id"])
                rule["expert_source"] = {k: doc.get(k) for k in ("id", "title", "source", "locator", "url")}
            rules.append(rule)
            conn.execute("INSERT OR REPLACE INTO settings VALUES('catalog',?)", (db.dump(rules),))
        r.update(status=decision, reviewer=user["actor"], reviewed_at=db.timestamp())
        conn.execute("UPDATE category_proposals SET body=? WHERE id=?", (db.dump(r), cid))
        db.audit(conn, user["actor"], "review_category", cid, decision=decision)
        return r


def analyze_input(body):
    from .sectors import adapt

    p = body.get("project")
    if not isinstance(p, dict) or not (p.get("title") or p.get("description") or p.get("documents")):
        raise ValueError("Podaj opis planowanej inwestycji lub dokument.")
    if not isinstance(body.get("filters", {}), dict):
        raise ValueError("Nieprawidłowy zestaw filtrów.")
    for field in ("title", "description", "location", "buyer", "type", "sector", "id"):
        if p.get(field) is not None and not isinstance(p[field], str):
            raise ValueError("Tytuł, opis i pola identyfikacyjne wymagają tekstu.")
    for field in ("documents", "observations", "sources", "events"):
        if field in p and (
            not isinstance(p[field], list)
            or len(p[field]) > 2500
            or any(not isinstance(v, dict) for v in p[field])
        ):
            raise ValueError("Dokumenty i zdarzenia wymagają listy rekordów.")
    for field in ("field_sources", "field_updated_at", "plan_snapshot"):
        if field in p and not isinstance(p[field], dict):
            raise ValueError("Nieprawidłowe metadane inwestycji.")
    with db.connection() as conn:
        cases = db.projects(conn)
        # Teaching data are never allowed to influence real investment analysis.
        cases = [c for c in cases if c.get("dataset") != "demo" or p.get("dataset") == "demo"]
        filters = body.get("filters") or {}
        count = 0
        if filters.get("preview_links") is True:
            cases, count = preview_cases(cases)
        p, cases, rules = adapt(p, cases, db.catalog(conn), db.sectors(conn))
        result = analysis.analyze_project(p, cases, rules, filters=filters)
        return mark_provisional(result, cases, count) if filters.get("preview_links") is True else result


@app.post("/api/analyze")
def analyze(body: dict = Body(...), user=Depends(identity)):
    result = analyze_input(body)
    aid = db.key("analysis", body, result)
    with db.connection(True) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO analyses VALUES(?,?,?)",
            (aid, db.timestamp(), db.dump({"input": body, "result": result})),
        )
    return {**result, "analysis_id": aid}


@app.get("/api/analyses/{aid}")
def get_analysis(aid: str, user=Depends(identity)):
    with db.connection() as conn:
        r = conn.execute("SELECT body FROM analyses WHERE id=?", (aid,)).fetchone()
        if not r:
            raise KeyError("Nie znaleziono analizy.")
        return json.loads(r[0])


@app.post("/api/analyses/{aid}/review")
def review_analysis(aid: str, body: dict = Body(...), user=Depends(role("expert"))):
    decision = body.get("decision")
    if decision not in {"accepted", "rejected"}:
        raise ValueError("Wybierz decyzję eksperta.")
    with db.connection(True) as conn:
        row = conn.execute("SELECT body FROM analyses WHERE id=?", (aid,)).fetchone()
        if not row:
            raise KeyError("Nie znaleziono analizy.")
        saved = json.loads(row[0])
        if saved["result"].get("preview_links") and decision == "accepted":
            raise ValueError("Zweryfikuj powiązania i oblicz analizę bez roboczego podglądu.")
        target = body.get("flag_id") or "all"
        if target != "all" and target not in {f["id"] for f in saved["result"]["flags"]}:
            raise ValueError("Nie znaleziono wniosku w zapisanej analizie.")
        assessment = dict(
            status=decision,
            actor=user["actor"],
            at=db.timestamp(),
            comment=str(body.get("comment", ""))[:4000],
        )
        saved.setdefault("reviews", {})[target] = assessment
        db.audit(conn, user["actor"], "review_analysis", aid, target=target, assessment=assessment)
        conn.execute("UPDATE analyses SET body=? WHERE id=?", (db.dump(saved), aid))
        return assessment


@app.post("/api/replay")
def replay(body: dict = Body(...), user=Depends(identity)):
    from .sectors import adapt

    spec = {
        "project_id": body.get("project_id"),
        "cutoff": body.get("cutoff"),
        "filters": body.get("filters") or {},
    }
    reveal = body.get("reveal") is True
    if body.get("replay_id"):
        with db.connection() as conn:
            row = conn.execute("SELECT body FROM replays WHERE id=?", (body["replay_id"],)).fetchone()
        if not row:
            raise KeyError("Nie znaleziono zapisanej próby.")
        saved = json.loads(row[0])
        if saved["spec"] != spec:
            raise HTTPException(409, "Zmieniono ustawienia. Uruchom nową próbę.")
        return {**saved["revealed" if reveal else "blind"], "replay_id": body["replay_id"]}
    with db.connection() as conn:
        p = db.project(conn, str(body.get("project_id") or ""))
        cases = [
            c for c in db.projects(conn) if (c.get("dataset") == "demo") == (p.get("dataset") == "demo")
        ]
        filters = body.get("filters") or {}
        if not isinstance(filters, dict):
            raise ValueError("Nieprawidłowe filtry analizy.")
        count = 0
        if filters.get("preview_links") is True:
            cases, count = preview_cases(cases)
            p = next(c for c in cases if c["id"] == p["id"])
        p, cases, rules = adapt(p, cases, db.catalog(conn), db.sectors(conn), as_of=body.get("cutoff"))
        result = analysis.run_backtest(p, cases, body.get("cutoff"), rules, reveal=True, filters=filters)
        if filters.get("preview_links") is True:
            mark_provisional(result, cases, count)
    blind = {**result, "replay": {"cutoff": result["replay"]["cutoff"], "revealed": False}}
    saved = {"spec": spec, "blind": blind, "revealed": result}
    rid = db.key("replay", saved)
    with db.connection(True) as conn:
        conn.execute("INSERT OR IGNORE INTO replays VALUES(?,?,?)", (rid, db.timestamp(), db.dump(saved)))
    return {**(result if reveal else blind), "replay_id": rid}


@app.post("/api/brief")
def brief(body: dict = Body(...), user=Depends(identity)):
    from .brief import create_brief

    if body.get("analysis_id"):
        saved = get_analysis(body["analysis_id"], user)
        project = saved["input"]["project"]
        result = {**saved["result"], "reviews": saved.get("reviews", {})}
    else:
        project = body.get("project") or {}
        result = analyze_input(body)
    return Response(
        create_brief(project, result, body.get("sensitivity_selection")),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="Risk-Miner-karta-inwestycji.docx"'},
    )


@app.get("/api/export")
def export(format: str = "json", project_id: str | None = None, user=Depends(identity)):
    with db.connection() as conn:
        cases = [
            detailed_view(p) for p in ([db.project(conn, project_id)] if project_id else db.projects(conn))
        ]
        review = [r for r in db.reviews(conn) if not project_id or r["project_id"] == project_id]
    if format == "json":
        payload = db.dump({"schema_version": 1, "projects": cases, "reviews": review})
        mime = "application/json"
    elif format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "project_id",
                "kind",
                "id",
                "title",
                "status",
                "source_id",
                "source_url",
                "locator",
                "record_json",
            ]
        )
        for p in cases:
            for kind, items in [("projects", [{k: v for k, v in p.items() if k not in db.GROUPS}])] + [
                (k, p[k]) for k in db.GROUPS
            ]:
                for it in items:
                    cells = [
                        p["id"],
                        kind,
                        it["id"],
                        it.get("title", ""),
                        it.get("status", ""),
                        it.get("source_id", ""),
                        it.get("url", ""),
                        it.get("locator", ""),
                        db.dump(it),
                    ]
                    writer.writerow(
                        [
                            "'" + str(c) if str(c).lstrip().startswith(("=", "+", "-", "@")) else c
                            for c in cells
                        ]
                    )
        payload = "\ufeff" + output.getvalue()
        mime = "text/csv"
    else:
        raise ValueError("Dostępne formaty to CSV i JSON.")
    return Response(
        payload,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="Risk-Miner.{format}"'},
    )


app.mount("/static", StaticFiles(directory=db.ROOT / "static"), name="static")
