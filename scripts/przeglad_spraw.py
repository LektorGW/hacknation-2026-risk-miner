"""Odtwarza podpisaną nazwą operatora weryfikację techniczną trzech spraw w kontenerze."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from riskminer import db, workflow

ACTOR = "Codex – weryfikacja techniczna"
PROJECTS = {"RM-2026-002", "RM-2026-005", "RM-2026-010"}


def validate(rows, existing):
    plan = []
    ids = set()
    for original in rows:
        r = dict(original)
        if r["review_id"] not in existing:
            if r.get("jury_merged_into") in existing:
                continue
            r.update(r.get("jury_variant", {}))
        rid = r["review_id"]
        old = existing.get(rid)
        keys = ("project_id", "source_id", "entity_id")
        if (
            not old
            or any(r[k] != old[k] for k in keys)
            or rid in ids
            or old["kind"] != r["group"]
        ):
            raise ValueError("Niezgodna tożsamość propozycji " + rid)
        ids.add(rid)
        if old.get("technical_assessment") == r["decision"] and old.get("technical_comment") == r["comment"]:
            continue
        previous_technical = (
            old.get("actor") == ACTOR
            and old["status"] == r["decision"]
            and old.get("comment") == r["comment"]
        )
        if not previous_technical and (
            old["status"] != "pending" or old["version"] != r["version"]
        ):
            raise ValueError("Rekord ma już inną decyzję " + rid)
        plan.append(r)
    if (
        ids != set(existing)
        or len(rows) != 71
        or {r["project_id"] for r in rows} != PROJECTS
    ):
        raise ValueError("Wykaz nie odpowiada bieżącej kolejce trzech spraw.")
    return plan


def review(rows, apply):
    with db.connection(write=apply) as conn:
        existing = {r["id"]: r for r in db.reviews(conn) if r["project_id"] in PROJECTS}
        for r in rows:
            source = db.entity(conn, r["source_id"])
            if (
                not source
                or hashlib.sha256(source["text"].encode()).hexdigest()
                != r["source_sha256"]
            ):
                raise ValueError("Zmienione źródło " + r["source_id"])
        plan = validate(rows, existing)
        print("Pozycje:", len(existing), "Do odtworzenia:", dict(Counter(r["decision"] for r in plan)))
        if not apply:
            return
        for r in plan:
            rid = r["review_id"]
            old = existing[rid]
            item = db.entity(conn, r["entity_id"])
            before = item.copy()
            item.update(r.get("patch", {}), status="pending", review_status="pending")
            item.pop("reviewed_at", None)
            item.pop("corrected_at", None)
            db.put_entity(conn, r["project_id"], r["group"], item)
            if r["group"] == "observations":
                source = db.entity(conn, r["source_id"])
                source.update(status="pending", review_status="pending")
                db.put_entity(conn, r["project_id"], "documents", source)
            old.update(
                technical_assessment=r["decision"],
                technical_comment=r["comment"],
                status="pending",
                payload=item,
                comment=r["comment"],
                actor=ACTOR,
                version=old["version"] + 1,
                updated_at=db.timestamp(),
            )
            conn.execute("UPDATE reviews SET status='pending',body=? WHERE id=?", (db.dump(old), rid))
            db.audit(
                conn,
                ACTOR,
                "technical_review",
                rid,
                suggestion=r["decision"],
                before=before,
                after=item,
                comment=r["comment"],
            )
        for pid in sorted({r["project_id"] for r in plan}):
            workflow.reconcile_relationships(conn, pid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    review(json.loads(args.manifest.read_text(encoding="utf-8-sig")), args.apply)
