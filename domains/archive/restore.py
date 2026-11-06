"""Local restore from archive ZIP (F13-LOCAL-2).

Restore keeps identity: the archive's ``document.id``/``document.source_id`` and
``doc_metadata`` (provenance) are written back untouched, so a restored row still
matches the per-source uniqueness contract and still says what produced it.

The write phase is all-or-nothing. A failure in any record rolls the whole
restore back and reports ``restored: 0``; a partial success is never reported as
if those rows had been committed.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.archive.service import check_zip_security, validate_archive_zip


def _load_articles(zip_path: str) -> list[dict[str, Any]]:
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        lines = [ln for ln in zf.read("articles.jsonl").decode("utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _as_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _same_record(art: Article, drec: dict[str, Any]) -> bool:
    doc = art.document
    if doc is None:
        return False
    return doc.content_hash == drec.get("content_hash") and doc.revision == drec.get("revision")


def restore_dry_run(db: Session, zip_path: str) -> dict[str, Any]:
    ok, sec_errors = check_zip_security(zip_path)
    if not ok:
        return {"ok": False, "errors": sec_errors}
    v = validate_archive_zip(zip_path)
    if not v.get("ok"):
        return {"ok": False, "errors": v.get("errors", [])}
    records = _load_articles(zip_path)
    existing = 0
    duplicates = 0
    conflicts = 0
    restorable = 0
    missing_source = 0
    invalid = 0
    for rec in records:
        key = _as_uuid(rec.get("article_id"))
        if key is None:
            invalid += 1
            continue
        drec = rec.get("document") or {}
        art = db.get(Article, key)
        if art is None:
            src_id = _as_uuid(drec.get("source_id"))
            if src_id is not None and db.get(Source, src_id) is None:
                missing_source += 1
                continue
            restorable += 1
            continue
        existing += 1
        if _same_record(art, drec):
            duplicates += 1
        else:
            conflicts += 1
    return {
        "ok": True,
        "total_records": len(records),
        "restorable": restorable,
        "existing": existing,
        "duplicates": duplicates,
        "conflicts": conflicts,
        "missing_source": missing_source,
        "invalid_records": invalid,
        "validation_errors": [],
    }


def restore_from_zip(db: Session, zip_path: str, *, dry_run: bool = False) -> dict[str, Any]:
    preview = restore_dry_run(db, zip_path)
    if not preview.get("ok"):
        return {"ok": False, "errors": preview.get("errors", []), "preview": preview}
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "preview": preview,
            "restored": 0,
            "skipped": 0,
            "conflicts": preview["conflicts"],
        }

    records = _load_articles(zip_path)
    restored = 0
    skipped = 0
    conflicts = 0
    errors: list[str] = []
    for rec in records:
        aid = rec.get("article_id")
        key = _as_uuid(aid)
        if key is None:
            errors.append(f"invalid article_id in archive: {aid!r}")
            continue
        drec = rec.get("document") or {}
        art = db.get(Article, key)
        if art is not None:
            if _same_record(art, drec):
                skipped += 1
            else:
                conflicts += 1
            continue
        # Restore Event + Claims + Evidence (if present in archive) before article.
        ev_rec = rec.get("event_record")
        if ev_rec and ev_rec.get("id"):
            ekey = _as_uuid(ev_rec.get("id"))
            if ekey is not None:
                from backend.database.models.claim import Claim, Evidence
                from backend.database.models.event import Event
                existing_ev = db.get(Event, ekey)
                if existing_ev is None:
                    occ = _as_dt(ev_rec.get("occurred_at"))
                    new_ev = Event(
                        id=ekey,
                        event_type=ev_rec.get("event_type"),
                        occurred_at=occ,
                        location=ev_rec.get("location"),
                        actors=ev_rec.get("actors"),
                        action=ev_rec.get("action"),
                        expected=ev_rec.get("expected"),
                        actual=ev_rec.get("actual"),
                        surprise=ev_rec.get("surprise"),
                        confidence=ev_rec.get("confidence"),
                    )
                    db.add(new_ev)
                    db.flush()
                for c in (ev_rec.get("claims") or []):
                    ckey = _as_uuid(c.get("id"))
                    if ckey is None:
                        continue
                    if db.get(Claim, ckey) is None:
                        new_claim = Claim(
                            id=ckey,
                            event_id=ekey,
                            subject=c.get("subject"),
                            predicate=c.get("predicate"),
                            object=c.get("object"),
                            claim_type=c.get("claim_type"),
                            confidence=c.get("confidence"),
                            verification_status=c.get("verification_status") or "unverified",
                        )
                        db.add(new_claim)
                        db.flush()
                    for e in (c.get("evidence") or []):
                        ekey2 = _as_uuid(e.get("id"))
                        if ekey2 is None or db.get(Evidence, ekey2) is not None:
                            continue
                        db.add(Evidence(
                            id=ekey2,
                            claim_id=ckey,
                            direction=e.get("direction", "supports"),
                            summary=e.get("summary"),
                            source_id=_as_uuid(e.get("source_id")),
                            document_id=_as_uuid(e.get("document_id")),
                            weight=e.get("weight"),
                            confidence=e.get("confidence"),
                        ))
                        db.flush()

        # Restore Entity + Graph edges (idempotent by id / unique constraint)
        for er in (rec.get("entity_records") or []):
            ekey = _as_uuid(er.get("id"))
            if ekey is None:
                continue
            from backend.database.models.entity import Entity
            if db.get(Entity, ekey) is None:
                existing = None
                try:
                    from sqlalchemy import select as _select
                    existing = db.execute(
                        _select(Entity).where(
                            Entity.type == er.get("type"),
                            Entity.canonical_name == er.get("canonical_name"),
                        )
                    ).scalars().first()
                except Exception:
                    existing = None
                if existing is None:
                    db.add(Entity(
                        id=ekey,
                        type=er.get("type") or "other",
                        canonical_name=er.get("canonical_name") or "",
                        display_name=er.get("display_name"),
                        aliases=er.get("aliases"),
                        country=er.get("country"),
                        description=er.get("description"),
                        source_id=_as_uuid(er.get("source_id")),
                    ))
                    db.flush()
        for ge in (rec.get("graph_edges") or []):
            gkey = _as_uuid(ge.get("id"))
            if gkey is None:
                continue
            from backend.database.models.entity import Entity, EntityRelationship
            if db.get(EntityRelationship, gkey) is not None:
                continue
            fe = _as_uuid(ge.get("from_entity_id"))
            te = _as_uuid(ge.get("to_entity_id"))
            if fe is None or te is None:
                continue
            if db.get(Entity, fe) is None or db.get(Entity, te) is None:
                continue
            db.add(EntityRelationship(
                id=gkey,
                from_entity_id=fe,
                to_entity_id=te,
                relation=ge.get("relation") or "other",
                weight=ge.get("weight"),
                confidence=ge.get("confidence"),
                valid_from=ge.get("valid_from"),
                valid_to=ge.get("valid_to"),
                evidence=ge.get("evidence"),
            ))
            db.flush()

        try:
            src_id = _as_uuid(drec.get("source_id"))
            if src_id is not None and db.get(Source, src_id) is None:
                raise ValueError(f"missing source {src_id} for article {aid}")
            doc = Document(
                id=_as_uuid(drec.get("id")) or uuid.uuid4(),
                source_id=src_id,
                url=drec.get("url"),
                title=drec.get("title"),
                raw_text=drec.get("raw_text"),
                raw_payload=drec.get("raw_payload"),
                content_hash=drec.get("content_hash"),
                hash=drec.get("hash"),
                revision=drec.get("revision"),
                doc_metadata=drec.get("doc_metadata"),
                language=drec.get("language"),
                author=drec.get("author"),
            )
            db.add(doc)
            db.flush()
            analysis = rec.get("analysis_results") or {}
            screening = rec.get("screening_results")
            new_art = Article(
                id=key,
                document_id=doc.id,
                title=rec.get("title"),
                summary=rec.get("summary"),
                language=rec.get("language"),
                source_name=rec.get("source_name"),
                country=rec.get("country"),
                topics=json.dumps(analysis["topics"]) if analysis.get("topics") is not None else rec.get("topics"),
                entities=json.dumps(analysis["entities"]) if analysis.get("entities") is not None else rec.get("entities"),
                sentiment=analysis.get("sentiment", rec.get("sentiment")),
                stance=analysis.get("stance", rec.get("stance")),
                importance=rec.get("importance"),
                decided_by=rec.get("decided_by"),
                confidence=rec.get("confidence"),
                uncertainty=rec.get("uncertainty"),
                duplicate_cluster=rec.get("duplicate_cluster"),
                event_cluster=rec.get("event_cluster"),
                event_id=_as_uuid((rec.get("relationships") or {}).get("event_id")) or _as_uuid((rec.get("event_record") or {}).get("id")),
                classification_status=rec.get("classification_status", "done"),
                classification_attempts=rec.get("classification_attempts", 0),
                classification_error=rec.get("classification_error"),
                classification_meta=(
                    json.dumps(screening) if screening is not None else rec.get("classification_meta")
                ),
                published_at=_as_dt(rec.get("published_at")),
                retrieved_at=_as_dt(rec.get("retrieved_at")),
                available_at=_as_dt(rec.get("available_at")),
            )
            db.add(new_art)
            db.flush()
            restored += 1
        except Exception as e:
            errors.append(f"restore error for {aid}: {e}")

    if errors:
        # All-or-nothing: nothing from this archive is kept, and the report says so.
        db.rollback()
        return {
            "ok": False,
            "dry_run": False,
            "restored": 0,
            "skipped": 0,
            "conflicts": conflicts,
            "errors": errors,
            "rolled_back": True,
        }
    db.commit()
    return {
        "ok": True,
        "dry_run": False,
        "restored": restored,
        "skipped": skipped,
        "conflicts": conflicts,
        "errors": [],
    }
