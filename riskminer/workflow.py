"""Translate imported evidence into project records and reviewable propositions."""

import hashlib
import re
import unicodedata
from datetime import date, datetime

from . import db
from .sectors import rules_for_sector


def fold(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower().replace("ł", "l"))
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c))))


def parse_date(value):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except (TypeError, ValueError):
            pass
    return None


def document_date(text):
    match = re.search(r"(?:dnia\s*|,\s*)(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})", text[:1600], re.I)
    return parse_date(match[1]) if match else None


def save_file(conn, name, data):
    fid = hashlib.sha256(data).hexdigest()
    conn.execute("INSERT OR IGNORE INTO files VALUES(?,?,?)", (fid, name, data))
    return fid


def make_project(conn, row, dataset):
    record_id = row.get("project_id") or row.get("record_id") or row.get("organizer_id") or row.get("id")
    if record_id and re.fullmatch(r"RM-\d{4}-\d{3}", str(record_id)):
        pid = record_id
    else:
        pid = db.key(
            "proj",
            row.get("cst") or row.get("bzp") or row.get("ocid") or fold(row.get("title")),
            fold(row.get("buyer")),
        )
    reserved = set(db.GROUPS) | {
        "id",
        "dataset",
        "source",
        "kind",
        "outcome_source_id",
        "plan_source_id",
        "field_sources",
    }
    project = {k: v for k, v in row.items() if k not in reserved}
    project.update(
        id=pid,
        dataset=dataset,
        title=row.get("title") or "Projekt bez tytułu",
        sector=row.get("sector") or "wodno-kanalizacyjny",
    )
    status = fold(row.get("status"))
    project["status"] = {
        "zakonczone": "completed",
        "zakonczony": "completed",
        "planowane": "planned",
        "w realizacji": "active",
    }.get(status, status or "planned")
    existing = conn.execute("SELECT body FROM projects WHERE id=?", (pid,)).fetchone()
    if not existing:
        db.put_project(conn, project)
    else:
        import json

        old = json.loads(existing[0])
        if str(project.get("as_of", "")) >= str(old.get("as_of", "")):
            changes = {
                k: v
                for k, v in project.items()
                if k not in {"dataset", "id"}
                and k not in old.get("field_updated_at", {})
                and old.get(k) != v
            }
            if changes:
                db.audit(
                    conn,
                    "import",
                    "update_source_record",
                    pid,
                    before={k: old.get(k) for k in changes},
                    after=changes,
                )
                db.put_project(conn, {**old, **changes})
    return pid


def insert_if_new(conn, pid, kind, item, review=False):
    if db.entity(conn, item["id"]):
        return False
    db.put_entity(conn, pid, kind, item)
    if review:
        db.enqueue(conn, pid, kind, item)
    return True


def add_events(conn, pid, doc, rules):
    from .analysis import extract_with_provider

    for proposal in extract_with_provider(doc, rules):
        obj = {
            **proposal,
            "source_id": doc["id"],
            "id": db.key(
                "evt", doc["id"], proposal.get("category"), proposal.get("excerpt"), proposal.get("title")
            ),
            "status": "pending",
        }
        insert_if_new(conn, pid, "events", obj, True)


def numeric_proposals(text):
    def find(pattern):
        return re.search(pattern, text, re.I | re.S)

    old = find(r"Dotychczasowy termin[^:\n]{0,80}:\s*(\d\d\.\d\d\.\d{4})")
    new = find(r"Proponowany nowy termin[^:\n]{0,80}:\s*(\d\d\.\d\d\.\d{4})")
    if old and new and parse_date(old[1]) and parse_date(new[1]):
        days = (date.fromisoformat(parse_date(new[1])) - date.fromisoformat(parse_date(old[1]))).days
        yield {
            "title": "Proponowane przesunięcie terminu",
            "metric": "requested_extension_days",
            "value": days,
            "unit": "dni",
            "excerpt": text[old.start() : new.end()],
        }
    patterns = [
        (
            r"Koszt robót dodatkowych[^\n]{0,65}?([\d][\d .\xa0]*,\d{2})\s*zł\s*brutto",
            "additional_cost_proposed",
            "Wartość proponowanych robót dodatkowych",
            "PLN brutto",
        ),
        (
            r"przedłużeni[aeu]\s+terminu\s+realizacji[^.]{0,65}?o\s+(?:okres\s+)?(\d+)\s+mies",
            "requested_extension_months",
            "Wnioskowana zmiana terminu umowy",
            "mies.",
        ),
        (
            r"przewidywane\s+opóźnienie\s+(\d+)\s+mies",
            "expected_service_delay_months",
            "Przewidywane opóźnienie efektu użytkowego",
            "mies.",
        ),
        (
            r"prośbą o wydłużenie terminu do\s*(\d\d\.\d\d\.\d{4})",
            "requested_deadline",
            "Wnioskowana data zakończenia",
            "data",
        ),
    ]
    for regex, metric, title, unit in patterns:
        match = find(regex)
        if match:
            number = match[1]
            value = (
                parse_date(number)
                if unit == "data"
                else float(re.sub(r"[\s.]", "", number).replace(",", "."))
            )
            yield dict(title=title, metric=metric, value=value, unit=unit, excerpt=match[0])


def attach(conn, pid, doc, rules):
    if not insert_if_new(conn, pid, "documents", doc):
        return False
    add_events(conn, pid, doc, rules)
    for m in numeric_proposals(doc.get("text", "")):
        item = {
            **m,
            "id": db.key("measure", doc["id"], m["metric"]),
            "source_id": doc["id"],
            "status": "pending",
            "description": m["excerpt"],
            "fact_type": "proposed",
        }
        insert_if_new(conn, pid, "measurements", item, True)
    return True


def identify(conn, text):
    from json import loads

    normalized = fold(text)
    words = set(normalized.split())
    scores = []
    for (raw,) in conn.execute("SELECT body FROM projects"):
        p = loads(raw)
        score = 0
        for name in ("cst", "ocid", "bzp", "public_id", "public_identifier"):
            part = fold(p.get(name))
            if part and len(part) > 7 and part in normalized:
                score = 3
        buyer = fold(p.get("buyer"))
        if buyer and len(buyer) > 6 and buyer in normalized:
            title_words = {t for t in fold(p.get("title")).split() if len(t) > 3}
            overlap = len(title_words & words) / max(1, len(title_words))
            if len(title_words & words) >= 3 and overlap >= 0.55:
                score = max(score, 2 + round(overlap, 2) / 2)
        if score:
            scores.append((score, p["id"]))
    scores.sort(reverse=True)
    if scores and (len(scores) == 1 or scores[0][0] > scores[1][0]):
        return scores[0][1]
    raise ValueError("Nie ustalono jednoznacznie projektu dokumentu. Wskaż inwestycję podczas importu.")


def import_rows(conn, name, data, rows, actor, pid=None, dataset="user"):
    if not rows:
        raise ValueError("Plik nie zawiera rekordów do importu.")
    if pid:
        db.project(conn, pid)
    fid = save_file(conn, name, data)
    touched = []
    is_doc = all(r.get("kind") == "document" for r in rows)
    if is_doc:
        fulltext = "\n".join(str(r.get("text", "")) for r in rows)
        explicit = bool(pid)
        pid = pid or identify(conn, fulltext)
        rules = rules_for_sector(db.project(conn, pid), db.catalog(conn), db.sectors(conn))
        published = document_date(fulltext)
        for r in rows:
            src = r.get("source") or {}
            locator = src.get("locator") or r.get("locator") or "Treść dokumentu"
            doc = dict(
                id=db.key("doc", pid, fid, locator),
                title=name,
                text=r.get("text", ""),
                source=name,
                url=f"/api/files/{fid}",
                locator=locator,
                published_at=r.get("published_at") or published,
                retrieved_at=db.timestamp(),
                status="accepted",
                file_id=fid,
                match_basis="Projekt wskazany podczas importu"
                if explicit
                else "Identyfikator lub zgodność zamawiającego i zakresu w treści",
            )
            attach(conn, pid, doc, rules)
        # Terms in Word often span paragraphs; retain one cross-paragraph calculation with both locators.
        if len(rows) > 1 and any(numeric_proposals(fulltext)):
            matches = [
                r
                for r in rows
                if re.search(r"dotychczasowy termin|proponowany nowy termin", str(r.get("text", "")), re.I)
            ]
            if len(matches) > 1:
                snippet = "\n".join(r["text"] for r in matches)
                locator = "; ".join(str(r.get("source", {}).get("locator", "")) for r in matches)
                doc = dict(
                    id=db.key("doc", pid, fid, "terms"),
                    title=name,
                    text=snippet,
                    source=name,
                    url=f"/api/files/{fid}",
                    locator=locator,
                    published_at=published,
                    retrieved_at=db.timestamp(),
                    status="accepted",
                    file_id=fid,
                )
                attach(conn, pid, doc, rules)
        touched.append(pid)
    else:
        if pid:
            raise ValueError("Arkusz inwestycji należy importować jako zbiór projektów.")
        for row in rows:
            if not row.get("title"):
                raise ValueError("Rekord projektu wymaga nazwy przedsięwzięcia.")
            rid = make_project(conn, row, dataset)
            src = row.get("source") or {}
            locator = src.get("locator", "Wiersz źródłowy")
            doc = dict(
                id=db.key("doc", rid, fid, locator),
                title=name,
                source=name,
                locator=locator,
                url=f"/api/files/{fid}",
                file_id=fid,
                status="accepted",
                retrieved_at=db.timestamp(),
                published_at=row.get("as_of") or row.get("record_date"),
                kind="registry",
                text=db.dump(row.get("raw") or {k: v for k, v in row.items() if k != "source"}),
            )
            insert_if_new(conn, rid, "documents", doc)
            base = db.project(conn, rid)
            if not base.get("registry_source_id") or str(row.get("as_of") or "") >= str(
                base.get("as_of") or ""
            ):
                base["registry_source_id"] = doc["id"]
                refs = base.setdefault("field_sources", {})
                for field in (
                    "actual_cost",
                    "planned_cost",
                    "planned_days",
                    "actual_days",
                    "completed_at",
                    "live_operation",
                    "type",
                ):
                    if field in row and field not in base.get("field_updated_at", {}):
                        refs[field] = doc["id"]
                db.put_project(conn, base)
            touched.append(rid)
    db.audit(
        conn, actor, "import", fid, filename=name, projects=list(dict.fromkeys(touched)), rows=len(rows)
    )
    return list(dict.fromkeys(touched))


def add_observations(conn, pid, items, actor):
    count = 0
    rules = rules_for_sector(db.project(conn, pid), db.catalog(conn), db.sectors(conn))
    for r in items:
        oid = db.key("obs", pid, r["source"], r["external_id"])
        docid = db.key(
            "doc", oid, r.get("sha256") or hashlib.sha256(str(r.get("text", "")).encode()).hexdigest()
        )
        doc = {
            k: v
            for k, v in r.items()
            if k
            in (
                "title",
                "text",
                "source",
                "url",
                "locator",
                "published_at",
                "retrieved_at",
                "external_id",
                "kind",
            )
        }
        doc.update(id=docid, status="pending")
        existing = db.entity(conn, oid)
        first = existing
        # A changed source becomes a new revision and must be reviewed.
        if existing and existing.get("source_id") != docid:
            oid = db.key("obs", oid, docid)
            existing = db.entity(conn, oid)
        if existing:
            # The snapshot may acquire a better official citation or a fuller excerpt.
            evidence = db.entity(conn, docid)
            if r.get("url") and (
                r["url"] != existing.get("url") or len(doc.get("text", "")) > len(evidence.get("text", ""))
            ):
                existing["url"] = evidence["url"] = r["url"]
                if len(doc.get("text", "")) > len(evidence.get("text", "")):
                    existing["text"] = evidence["text"] = doc["text"]
                db.put_entity(conn, pid, "documents", evidence)
                db.put_entity(conn, pid, "observations", existing)
                row = conn.execute("SELECT id,body FROM reviews WHERE entity_id=?", (oid,)).fetchone()
                if row:
                    import json

                    reviewed = json.loads(row[1])
                    reviewed["payload"] = existing
                    conn.execute("UPDATE reviews SET body=? WHERE id=?", (db.dump(reviewed), row[0]))
            continue
        obj = {**r, "id": oid, "source_id": docid, "status": "pending"}
        if first and first["source_id"] != docid:
            obj["revision_of"] = first["id"]
            prior = [
                v
                for v in db.project(conn, pid)["observations"]
                if v.get("external_id") == r["external_id"]
                and v.get("source") == r["source"]
                and v.get("status") != "superseded"
            ]
            # Replaying an older archive must never retire a freshly retrieved notice.
            if any(str(v.get("retrieved_at") or "") > str(r.get("retrieved_at") or "") for v in prior):
                continue
            for old in prior:
                evidence = db.entity(conn, old["source_id"])
                old["status"] = evidence["status"] = "superseded"
                old["review_status"] = evidence["review_status"] = "superseded"
                db.put_entity(conn, pid, "documents", evidence)
                db.put_entity(conn, pid, "observations", old)
                for review in conn.execute(
                    "SELECT id,body FROM reviews WHERE project_id=? AND (entity_id=? OR json_extract(body,'$.source_id')=?)",
                    (pid, old["id"], old["source_id"]),
                ).fetchall():
                    import json

                    previous = json.loads(review[1])
                    previous.update(
                        status="superseded", updated_at=db.timestamp(), version=previous["version"] + 1
                    )
                    conn.execute(
                        "UPDATE reviews SET status=?,body=? WHERE id=?",
                        ("superseded", db.dump(previous), review[0]),
                    )
                db.audit(
                    conn,
                    actor,
                    "replace_source",
                    old["id"],
                    previous_source=old["source_id"],
                    new_source=docid,
                )
        attach(conn, pid, doc, rules)
        materialize_notice(conn, pid, obj)
        if insert_if_new(conn, pid, "observations", obj, True):
            count += 1
    db.audit(conn, actor, "enrich", pid, found=len(items), added=count)
    reconcile_relationships(conn, pid)
    return count


def correct_contract(conn, pid, item, cid):
    """Keep the operator's mapping separate from the identifier printed in the notice."""
    target = db.entity(conn, cid) if cid else None
    if cid and (not target or target.get("project_id") != pid):
        raise ValueError("Wybrana umowa musi należeć do tej inwestycji.")
    item.setdefault("original_contract_key", item.get("contract_key"))
    item["contract_id"] = cid or None
    item["contract_key"] = target.get("external_id") if target else None


def materialize_notice(conn, pid, notice):
    """Only records that carry a real source identifier can establish an entity."""
    procedure = notice.get("procedure_key") or notice.get("ocid")
    if not procedure:
        return
    proc_id = db.key("proc", pid, procedure)
    base = {
        "source_id": notice["source_id"],
        "status": notice["status"],
        "url": notice.get("url"),
        "published_at": notice.get("published_at"),
    }

    def related(group, obj):
        previous = db.entity(conn, obj["id"])
        if not previous or (previous.get("status") != "accepted" and obj["status"] == "accepted"):
            db.put_entity(conn, pid, group, obj)

    related("procedures", dict(base, id=proc_id, title=notice["title"], external_id=procedure))
    for award in notice.get("awards", []):
        if award.get("contract_key"):
            aid = db.key("ctr", pid, procedure, award["contract_key"])
            title = f"Umowa z {award.get('signed_on', '?')}"
            if award.get("lot"):
                title += f" · część {award['lot']}"
            related(
                "contracts",
                dict(
                    base,
                    **award,
                    id=aid,
                    title=title,
                    procedure_id=proc_id,
                    external_id=award["contract_key"],
                ),
            )
    contract = notice.get("contract_key")
    contract_id = None
    if contract:
        contract_id = db.key("ctr", pid, procedure, contract)
        related(
            "contracts",
            dict(
                base,
                id=contract_id,
                procedure_id=proc_id,
                title=f"Umowa z {notice.get('facts', {}).get('signed_on', '?')}",
                external_id=contract,
            ),
        )
    notice.update(procedure_id=proc_id)
    if contract_id:
        notice["contract_id"] = contract_id
    if notice.get("kind") in ("change", "contract_change", "amendment", "contract_modification"):
        related(
            "changes",
            dict(
                base,
                id=db.key("change", notice["id"]),
                procedure_id=proc_id,
                contract_id=contract_id,
                title=notice["title"],
                description=notice.get("text", ""),
            ),
        )


def reconcile_relationships(conn, pid):
    """Recompute relation states after withdrawing or correcting source links."""
    p = db.project(conn, pid)
    for group, field in (
        ("procedures", "procedure_id"),
        ("contracts", "contract_id"),
        ("changes", "source_id"),
    ):
        for item in p[group]:
            supporters = [
                r
                for r in p["observations"]
                if (r.get(field) == (item["source_id"] if group == "changes" else item["id"]))
                or (
                    group == "contracts"
                    and any(a.get("contract_key") == item.get("external_id") for a in r.get("awards", []))
                )
            ]
            active = [r for r in supporters if r.get("status") == "accepted"] or [
                r for r in supporters if r.get("status") == "pending"
            ]
            updated = {**item, "status": active[0]["status"] if active else "rejected"}
            if active:
                updated["source_id"] = active[0]["source_id"]
                updated["url"] = active[0].get("url")
            if updated != item:
                db.put_entity(conn, pid, group, updated)
