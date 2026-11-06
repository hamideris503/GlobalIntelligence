"""Local-first archive core (F13).

Scope: measurement, eligibility, ZIP building, validation, optional splitting.
No Telegram, no purge, no deletion of source data.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.document import Document, provenance_of
from backend.database.models.job import JobRun

MAX_ZIP_BYTES_DEFAULT = 18_000_000


def purge_candidates(db: Session) -> list[str]:
    """Articles eligible for purge (dry-run only). Never deletes."""
    arts = db.execute(select(Article)).scalars().all()
    out = []
    for a in arts:
        ok, reasons = is_eligible(db, a)
        if ok:
            out.append(str(a.id))
    return out


def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def archive_settings() -> dict[str, Any]:
    return {
        "ARCHIVE_ENABLED": env_bool("ARCHIVE_ENABLED", False),
        "TELEGRAM_ARCHIVE_ENABLED": env_bool("TELEGRAM_ARCHIVE_ENABLED", False),
        "ARCHIVE_AUTO_PURGE_ENABLED": env_bool("ARCHIVE_AUTO_PURGE_ENABLED", False),
        "PURGE_DRY_RUN": env_bool("PURGE_DRY_RUN", True),
        "ARCHIVE_MAX_ZIP_BYTES": int(os.getenv("ARCHIVE_MAX_ZIP_BYTES", str(MAX_ZIP_BYTES_DEFAULT))),
    }


def measure_storage(db: Session) -> dict[str, Any]:
    def count(model) -> int:
        return int(db.execute(select(func.count()).select_from(model)).scalar() or 0)

    from backend.database.models.event import Event
    from backend.database.models.memory import MemoryRecord
    from backend.database.models.source import Source

    articles = db.execute(select(Article)).scalars().all()
    docs = db.execute(select(Document)).scalars().all()

    def text_bytes(rows, fields):
        total = 0
        for r in rows:
            for f in fields:
                v = getattr(r, f, None)
                if isinstance(v, str):
                    total += len(v.encode("utf-8"))
        return total

    import shutil as _shutil
    try:
        du = _shutil.disk_usage(os.getcwd())
        disk = {"total": du.total, "used": du.used, "free": du.free}
    except Exception:
        disk = None

    return {
        "disk_usage": disk,
        "counts": {
            "articles": count(Article),
            "documents": count(Document),
            "sources": count(Source),
            "events": count(Event),
            "memory_records": count(MemoryRecord),
            "article_dispatches": count(ArticleDispatch),
            "job_runs": count(JobRun),
        },
        "approx_text_bytes": {
            "articles": text_bytes(articles, ["title", "summary", "topics", "entities", "classification_meta"]),
            "documents": text_bytes(docs, ["raw_payload", "raw_text", "title"]),
        },
        "archive_settings": archive_settings(),
    }


def _active_dispatches(db: Session, article_id) -> list[ArticleDispatch]:
    return db.execute(
        select(ArticleDispatch).where(
            ArticleDispatch.article_id == article_id,
            ArticleDispatch.status.in_(("pending", "retryable", "running", "claimed")),
        )
    ).scalars().all()


def is_eligible(db: Session, article: Article) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if article.classification_status != "done":
        reasons.append("classification_not_done")
    if _active_dispatches(db, article.id):
        reasons.append("active_dispatch")
    doc = article.document
    if doc is None:
        reasons.append("missing_document")
    else:
        if not doc.raw_text:
            reasons.append("missing_raw_text")
        if not (doc.content_hash or doc.hash):
            reasons.append("missing_content_hash")
        if provenance_of(doc.doc_metadata) == "unknown":
            reasons.append("unknown_provenance")
    # dependency check: event must exist if referenced
    if article.event_id is not None:
        from backend.database.models.event import Event
        ev = db.get(Event, article.event_id)
        if ev is None:
            reasons.append("missing_event_dependency")
    if article.importance is None:
        reasons.append("missing_priority")
    if not article.classification_meta:
        reasons.append("missing_screening_meta")
    if article.importance is not None and article.importance <= 2:
        reasons.append("protected_priority_p0_p1")
    if article.uncertainty is not None and article.uncertainty > 0.5:
        reasons.append("high_uncertainty")
    return (len(reasons) == 0, reasons)


def eligibility_status(reasons: list[str]) -> str:
    if not reasons:
        return "ELIGIBLE"
    if "active_dispatch" in reasons or "classification_not_done" in reasons:
        # distinguish pending vs active
        if "classification_not_done" in reasons:
            return "BLOCKED_PENDING"
        return "BLOCKED_ACTIVE_JOB"
    if any(r in reasons for r in ("missing_raw_text", "missing_document", "missing_content_hash", "unknown_provenance")):
        return "BLOCKED_MISSING_PROVENANCE"
    if any(r in reasons for r in ("missing_priority", "missing_screening_meta", "missing_event_dependency")):
        return "BLOCKED_MISSING_DEPENDENCY"
    if any(r in reasons for r in ("protected_priority_p0_p1", "high_uncertainty")):
        return "BLOCKED_PROTECTED"
    if "revision_changed" in reasons:
        return "BLOCKED_REVISION_CHANGED"
    return "BLOCKED_MISSING_DEPENDENCY"


@dataclass
class ArchiveResult:
    zip_path: str
    manifest: dict[str, Any]
    article_ids: list[str]
    omitted: list[dict[str, Any]] = field(default_factory=list)
    sha256: str = ""


def _parse_json(v):
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return v


def _article_record(db: Session, a: Article) -> dict[str, Any]:
    doc = a.document
    source = getattr(doc, "source", None) if doc else None
    # Event + claims + evidence (if referenced)
    # Entity + graph edges (conservative: names in article.entities + claim subjects/objects)
    from backend.database.models.entity import Entity, EntityRelationship
    selected_names = set()
    try:
        ents = json.loads(a.entities) if a.entities else []
        if isinstance(ents, list):
            for e in ents:
                if isinstance(e, str):
                    selected_names.add(e)
                elif isinstance(e, dict):
                    selected_names.add(e.get("name") or e.get("canonical_name"))
    except Exception:
        pass
    event_for_entities = None
    if a.event_id is not None:
        from backend.database.models.event import Event
        event_for_entities = db.get(Event, a.event_id)
    claims_for_entities = []
    if event_for_entities is not None:
        from backend.database.models.claim import Claim
        claims_for_entities = db.execute(select(Claim).where(Claim.event_id == event_for_entities.id)).scalars().all()
        for c in claims_for_entities:
            if c.subject:
                selected_names.add(c.subject)
            if c.object:
                selected_names.add(c.object)
    ent_rows = []
    if selected_names:
        ent_rows = db.execute(
            select(Entity).where(Entity.canonical_name.in_(selected_names))
        ).scalars().all()
    entity_records = [
        {
            "id": str(e.id),
            "type": e.type,
            "canonical_name": e.canonical_name,
            "display_name": e.display_name,
            "aliases": e.aliases,
            "country": e.country,
            "description": e.description,
            "source_id": str(e.source_id) if e.source_id else None,
        }
        for e in ent_rows
    ]
    ent_ids = {e.id for e in ent_rows}
    edge_rows = []
    if ent_ids:
        edge_rows = db.execute(
            select(EntityRelationship).where(
                EntityRelationship.from_entity_id.in_(ent_ids),
                EntityRelationship.to_entity_id.in_(ent_ids),
            )
        ).scalars().all()
    graph_edges = [
        {
            "id": str(e.id),
            "from_entity_id": str(e.from_entity_id),
            "to_entity_id": str(e.to_entity_id),
            "relation": e.relation,
            "weight": e.weight,
            "confidence": e.confidence,
            "valid_from": e.valid_from,
            "valid_to": e.valid_to,
            "evidence": e.evidence,
        }
        for e in edge_rows
    ]

    event_record = None
    if a.event_id is not None:
        from backend.database.models.claim import Claim, Evidence
        from backend.database.models.event import Event
        ev = db.get(Event, a.event_id)
        if ev is not None:
            claims = db.execute(select(Claim).where(Claim.event_id == ev.id)).scalars().all()
            claims_out = []
            for c in claims:
                evids = db.execute(select(Evidence).where(Evidence.claim_id == c.id)).scalars().all()
                claims_out.append({
                    "id": str(c.id),
                    "subject": c.subject,
                    "predicate": c.predicate,
                    "object": c.object,
                    "claim_type": c.claim_type,
                    "confidence": c.confidence,
                    "verification_status": c.verification_status,
                    "evidence": [
                        {
                            "id": str(e.id),
                            "direction": e.direction,
                            "summary": e.summary,
                            "source_id": str(e.source_id) if e.source_id else None,
                            "document_id": str(e.document_id) if e.document_id else None,
                            "weight": e.weight,
                            "confidence": e.confidence,
                        }
                        for e in evids
                    ],
                })
            event_record = {
                "id": str(ev.id),
                "event_type": ev.event_type,
                "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
                "location": ev.location,
                "actors": ev.actors,
                "action": ev.action,
                "expected": ev.expected,
                "actual": ev.actual,
                "surprise": ev.surprise,
                "confidence": ev.confidence,
                "claims": claims_out,
            }
    dispatches = db.execute(
        select(ArticleDispatch).where(ArticleDispatch.article_id == a.id)
    ).scalars().all()
    return {
        "article_id": str(a.id),
        "document_id": str(a.document_id) if a.document_id else None,
        "event_id": str(a.event_id) if a.event_id else None,
        "title": a.title,
        "summary": a.summary,
        "language": a.language,
        "source_name": a.source_name,
        "country": a.country,
        "topics": a.topics,
        "entities": a.entities,
        "sentiment": a.sentiment,
        "stance": a.stance,
        "importance": a.importance,
        "decided_by": a.decided_by,
        "confidence": a.confidence,
        "uncertainty": a.uncertainty,
        "duplicate_cluster": a.duplicate_cluster,
        "event_cluster": a.event_cluster,
        "classification_status": a.classification_status,
        "classification_attempts": a.classification_attempts,
        "classification_error": a.classification_error,
        "classification_meta": a.classification_meta,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "available_at": a.available_at.isoformat() if getattr(a, "available_at", None) else None,
        "published_at": a.published_at.isoformat() if getattr(a, "published_at", None) else None,
        "retrieved_at": a.retrieved_at.isoformat() if getattr(a, "retrieved_at", None) else None,
        "document": {
            "id": str(doc.id) if doc else None,
            "source_id": str(doc.source_id) if doc and doc.source_id else None,
            "url": doc.url if doc else None,
            "title": doc.title if doc else None,
            "raw_payload": doc.raw_payload if doc else None,
            "raw_text": doc.raw_text if doc else None,
            "language": doc.language if doc else None,
            "author": doc.author if doc else None,
            "revision": doc.revision if doc else None,
            "hash": doc.hash if doc else None,
            "content_hash": doc.content_hash if doc else None,
            "doc_metadata": doc.doc_metadata if doc else None,
            "provenance": provenance_of(doc.doc_metadata) if doc else "unknown",
            "created_at": doc.created_at.isoformat() if doc and doc.created_at else None,
        },
        "source": {
            "id": str(source.id) if (source := getattr(doc, "source", None)) else None,
            "name": getattr(source, "name", None) if source else None,
            "domain": getattr(source, "domain", None) if source else None,
            "type": getattr(source, "type", None) if source else None,
        } if source else None,
        "screening_results": _parse_json(a.classification_meta),
        "priority_decisions": {
            "importance": a.importance,
            "decided_by": a.decided_by,
            "confidence": a.confidence,
            "uncertainty": a.uncertainty,
            "priority_source": getattr(doc, "priority_source", None) if doc else None,
            "priority_status": getattr(doc, "priority_status", None) if doc else None,
            "priority_reason": getattr(doc, "priority_reason", None) if doc else None,
        },
        "analysis_results": {
            "topics": _parse_json(a.topics),
            "entities": _parse_json(a.entities),
            "sentiment": a.sentiment,
            "stance": a.stance,
            "summary": a.summary,
        },
        "relationships": {
            "event_id": str(a.event_id) if a.event_id else None,
            "duplicate_cluster": a.duplicate_cluster,
            "event_cluster": a.event_cluster,
        },
        "event_record": event_record,
        "entity_records": entity_records,
        "graph_edges": graph_edges,
        "processing_history": {
            "classification_status": a.classification_status,
            "classification_attempts": a.classification_attempts,
            "classification_error": a.classification_error,
            "dispatches": [
                {"id": str(d.id), "task_name": d.task_name, "status": d.status,
                 "attempts": d.attempts, "last_error": d.last_error}
                for d in dispatches
            ],
        },
    }


def build_archive_zip(db: Session, article_ids: list[str], out_path: str, batch_id: str | None = None) -> ArchiveResult:
    import uuid as _uuid
    articles = []
    for aid in article_ids:
        try:
            key = _uuid.UUID(str(aid))
        except (ValueError, AttributeError):
            key = aid
        a = db.get(Article, key)
        if a is not None:
            articles.append(a)

    eligible_list = []
    omitted = []
    for a in articles:
        ok, reasons = is_eligible(db, a)
        if ok:
            eligible_list.append(a)
        else:
            omitted.append({"article_id": str(a.id), "reasons": reasons})

    articles_lines = [json.dumps(_article_record(db, a), ensure_ascii=False) for a in eligible_list]
    screening_lines = [json.dumps({"article_id": str(a.id), "screening": _parse_json(a.classification_meta)}, ensure_ascii=False) for a in eligible_list]
    priority_lines = [json.dumps({"article_id": str(a.id), "priority": {
        "importance": a.importance, "decided_by": a.decided_by,
        "confidence": a.confidence, "uncertainty": a.uncertainty,
    }}, ensure_ascii=False) for a in eligible_list]
    analysis_lines = [json.dumps({"article_id": str(a.id), "analysis": {
        "topics": _parse_json(a.topics), "entities": _parse_json(a.entities),
        "sentiment": a.sentiment, "stance": a.stance, "summary": a.summary,
    }}, ensure_ascii=False) for a in eligible_list]
    rel_lines = [json.dumps({"article_id": str(a.id), "relationships": {
        "event_id": str(a.event_id) if a.event_id else None,
        "duplicate_cluster": a.duplicate_cluster, "event_cluster": a.event_cluster,
    }}, ensure_ascii=False) for a in eligible_list]
    src_lines = [json.dumps({"article_id": str(a.id), "source_and_provenance": {
        "document_id": str(a.document_id) if a.document_id else None,
        "source_id": str(a.document.source_id) if a.document and a.document.source_id else None,
        "provenance": provenance_of(a.document.doc_metadata) if a.document else "unknown",
        "content_hash": a.document.content_hash if a.document else None,
        "hash": a.document.hash if a.document else None,
        "revision": a.document.revision if a.document else None,
    }}, ensure_ascii=False) for a in eligible_list]
    proc_lines = [json.dumps({"article_id": str(a.id), "processing_history": {
        "classification_status": a.classification_status,
        "classification_attempts": a.classification_attempts,
    }}, ensure_ascii=False) for a in eligible_list]
    omissions_lines = [json.dumps(o, ensure_ascii=False) for o in omitted]

    manifest = {
        "batch_id": batch_id or os.path.basename(out_path),
        "created_at": datetime.now(UTC).isoformat(),
        "article_count": len(eligible_list),
        "omitted_count": len(omitted),
        "article_ids": [str(a.id) for a in eligible_list],
        "max_zip_bytes": archive_settings()["ARCHIVE_MAX_ZIP_BYTES"],
        "mock_as_real": False,
    }

    files = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2),
        "articles.jsonl": "\n".join(articles_lines) + ("\n" if articles_lines else ""),
        "screening_results.jsonl": "\n".join(screening_lines) + ("\n" if screening_lines else ""),
        "priority_decisions.jsonl": "\n".join(priority_lines) + ("\n" if priority_lines else ""),
        "analysis_results.jsonl": "\n".join(analysis_lines) + ("\n" if analysis_lines else ""),
        "relationships.jsonl": "\n".join(rel_lines) + ("\n" if rel_lines else ""),
        "source_and_provenance.jsonl": "\n".join(src_lines) + ("\n" if src_lines else ""),
        "processing_history.jsonl": "\n".join(proc_lines) + ("\n" if proc_lines else ""),
        "archive_omissions.jsonl": "\n".join(omissions_lines) + ("\n" if omissions_lines else ""),
    }

    sha_lines = []
    for name, content in files.items():
        sha_lines.append(f"{hashlib.sha256(content.encode('utf-8')).hexdigest()}  {name}")
    files["SHA256SUMS.txt"] = "\n".join(sha_lines) + "\n"

    report = "# Archive Report\n\n"
    report += f"- Articles archived: {len(eligible_list)}\n"
    report += f"- Omitted: {len(omitted)}\n"
    report += f"- Created: {manifest['created_at']}\n"
    files["REPORT.md"] = report

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)

    h = hashlib.sha256()
    with open(out_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    return ArchiveResult(
        zip_path=out_path,
        manifest=manifest,
        article_ids=[str(a.id) for a in eligible_list],
        omitted=omitted,
        sha256=h.hexdigest(),
    )


def estimate_article_bytes(db: Session, a: Article) -> int:
    rec = _article_record(db, a)
    return len(json.dumps(rec, ensure_ascii=False).encode("utf-8"))


def chunk_article_ids(db: Session, article_ids: list[str], max_bytes: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for aid in article_ids:
        try:
            key = uuid.UUID(str(aid))
        except (ValueError, AttributeError):
            key = aid
        a = db.get(Article, key)
        size = estimate_article_bytes(db, a) if a is not None else 1024
        if current and current_size + size > max_bytes:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(aid)
        current_size += size
    if current:
        chunks.append(current)
    if not chunks:
        chunks = [[]]
    return chunks


def build_archive_zips(db: Session, article_ids: list[str], out_dir: str, batch_id: str | None = None) -> list[ArchiveResult]:
    parent = batch_id or ("batch-" + datetime.now(UTC).strftime("%Y%m%d%H%M%S"))
    max_bytes = archive_settings()["ARCHIVE_MAX_ZIP_BYTES"]
    chunks = chunk_article_ids(db, article_ids, max_bytes)
    results: list[ArchiveResult] = []
    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        part_name = f"{parent}.part{idx+1}of{total}.zip"
        out_path = os.path.join(out_dir, part_name)
        res = build_archive_zip(db, chunk, out_path, batch_id=f"{parent}::part{idx+1}/{total}")
        _patch_part_manifest(out_path, idx + 1, total, parent)
        results.append(res)
    return results


def _patch_part_manifest(path: str, part: int, total: int, parent: str) -> None:
    with zipfile.ZipFile(path, "r") as zin:
        items = {n: zin.read(n) for n in zin.namelist()}
    manifest = json.loads(items["manifest.json"])
    manifest["part_index"] = part
    manifest["total_parts"] = total
    manifest["parent_batch_id"] = parent
    items["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    sha_lines = []
    for name, content in items.items():
        if name == "SHA256SUMS.txt":
            continue
        sha_lines.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
    items["SHA256SUMS.txt"] = ("\n".join(sha_lines) + "\n").encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, content in items.items():
            zout.writestr(name, content)


def check_zip_security(path: str, max_bytes: int | None = None) -> tuple[bool, list[str]]:
    """Security checks for an untrusted ZIP."""
    max_bytes = max_bytes or archive_settings()["ARCHIVE_MAX_ZIP_BYTES"]
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > 10000:
                errors.append("too many entries")
            total_uncompressed = 0
            for info in infos:
                name = info.filename
                if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                    errors.append(f"unsafe path: {name}")
                if info.file_size > max_bytes:
                    errors.append(f"entry too large: {name}")
                total_uncompressed += info.file_size
            if total_uncompressed > max_bytes * 10:
                errors.append("possible zip bomb: total uncompressed too large")
            # ratio check
            compressed_size = os.path.getsize(path)
            if compressed_size > 0 and total_uncompressed / compressed_size > 100:
                errors.append("possible zip bomb: high compression ratio")
    except Exception as e:
        errors.append(f"zip security check error: {e}")
    return (len(errors) == 0, errors)


def validate_archive_zip(path: str) -> dict[str, Any]:
    errors: list[str] = []
    result: dict[str, Any] = {"ok": False, "errors": errors, "files": [], "counts": {}}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            result["files"] = zf.namelist()
            bad = zf.testzip()
            if bad is not None:
                errors.append(f"corrupt entry: {bad}")
            required = [
                "manifest.json", "articles.jsonl", "screening_results.jsonl",
                "priority_decisions.jsonl", "analysis_results.jsonl", "relationships.jsonl",
                "source_and_provenance.jsonl", "processing_history.jsonl",
                "archive_omissions.jsonl", "SHA256SUMS.txt", "REPORT.md",
            ]
            for r in required:
                if r not in result["files"]:
                    errors.append(f"missing file: {r}")
            manifest = {}
            if "manifest.json" in result["files"]:
                try:
                    manifest = json.loads(zf.read("manifest.json"))
                except Exception as e:
                    errors.append(f"manifest parse error: {e}")
            result["manifest"] = manifest
            if "SHA256SUMS.txt" in result["files"]:
                try:
                    sums_text = zf.read("SHA256SUMS.txt").decode("utf-8")
                    for line in sums_text.strip().splitlines():
                        parts = line.split("  ", 1)
                        if len(parts) != 2:
                            continue
                        expected, fname = parts
                        if fname in result["files"]:
                            actual = hashlib.sha256(zf.read(fname)).hexdigest()
                            if actual != expected:
                                errors.append(f"sha256 mismatch: {fname}")
                except Exception as e:
                    errors.append(f"sha256 check error: {e}")
            if manifest:
                articles_lines = [ln for ln in zf.read("articles.jsonl").decode("utf-8").splitlines() if ln.strip()]
                if len(articles_lines) != manifest.get("article_count", -1):
                    errors.append(f"article count mismatch: {len(articles_lines)} vs {manifest.get('article_count')}")
                ids = []
                for ln in articles_lines:
                    try:
                        ids.append(json.loads(ln)["article_id"])
                    except Exception:
                        errors.append("bad article json line")
                if len(set(ids)) != len(ids):
                    errors.append("duplicate article_id in archive")
                result["counts"] = {"articles": len(articles_lines)}
            if manifest.get("mock_as_real"):
                errors.append("manifest claims mock_as_real=true")
    except Exception as e:
        errors.append(f"zip open error: {e}")
    result["ok"] = len(errors) == 0
    return result
