"""Archive catalog persistence (F13-LOCAL-2)."""
from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy.orm import Session

from backend.database.models.archive_catalog import ArchiveArticle, ArchiveCatalog
from domains.archive.service import validate_archive_zip


def _archive_fingerprints(zip_path: str) -> dict[str, tuple[int | None, str | None]]:
    """Map article_id -> (revision, content_hash) as recorded inside the archive.

    Read from the archive rather than the live DB so the catalog describes what
    was actually shipped; a later mutation of the live row must not silently
    rewrite the fingerprint that conflict detection depends on.
    """
    import zipfile

    out: dict[str, tuple[int | None, str | None]] = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            lines = zf.read("articles.jsonl").decode("utf-8").splitlines()
    except (KeyError, OSError, zipfile.BadZipFile):
        return out
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        doc = rec.get("document") or {}
        out[str(rec.get("article_id"))] = (doc.get("revision"), doc.get("content_hash"))
    return out


def record_archive(db: Session, result_manifest: dict[str, Any], zip_path: str,
                   article_ids: list[str], omitted: list[dict[str, Any]],
                   eligibility: dict[str, str] | None = None) -> ArchiveCatalog:
    eligibility = eligibility or {}
    size = os.path.getsize(zip_path) if os.path.exists(zip_path) else None
    sha = None
    # compute sha256
    import hashlib
    if os.path.exists(zip_path):
        h = hashlib.sha256()
        with open(zip_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        sha = h.hexdigest()

    v = validate_archive_zip(zip_path)
    status = "valid" if v.get("ok") else "invalid"

    row = ArchiveCatalog(
        archive_id=str(result_manifest.get("batch_id") or os.path.basename(zip_path)),
        batch_id=result_manifest.get("batch_id"),
        parent_batch_id=result_manifest.get("parent_batch_id"),
        part_index=result_manifest.get("part_index"),
        total_parts=result_manifest.get("total_parts"),
        schema_version="1.0",
        file_name=os.path.basename(zip_path),
        file_size=size,
        sha256=sha,
        archive_path=zip_path,
        manifest_json=json.dumps(result_manifest, ensure_ascii=False),
        validation_status=status,
        restore_status="not_restored",
        telegram_status="not_sent",
        article_count=result_manifest.get("article_count", 0),
        record_counts_json=json.dumps({"articles": result_manifest.get("article_count", 0),
                                     "omitted": len(omitted)}),
    )
    db.add(row)
    db.flush()

    fingerprints = _archive_fingerprints(zip_path)
    for aid in article_ids:
        revision, content_hash = fingerprints.get(str(aid), (None, None))
        ar = ArchiveArticle(
            archive_id=row.archive_id,
            original_article_id=aid,
            revision=revision,
            content_hash=content_hash,
            eligibility_reason=eligibility.get(aid, "ELIGIBLE"),
            eligibility_status="ELIGIBLE",
            archive_status="archived",
            restore_status="not_restored",
            archived_at=result_manifest.get("created_at"),
        )
        db.add(ar)
    db.commit()
    db.refresh(row)
    return row


def get_archive(db: Session, archive_id: str) -> ArchiveCatalog | None:
    return db.query(ArchiveCatalog).filter(ArchiveCatalog.archive_id == archive_id).first()


def list_archives(db: Session) -> list[ArchiveCatalog]:
    return db.query(ArchiveCatalog).order_by(ArchiveCatalog.created_at.desc()).all()
