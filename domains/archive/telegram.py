"""Telegram transport for F13 Smart Archive (live, credential-gated)."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.archive_catalog import ArchiveCatalog

logger = get_logger(__name__)

MAX_FILE_BYTES = 50 * 1024 * 1024  # Telegram bot API limit


def _env(name: str) -> str | None:
    v = os.getenv(name)
    return v.strip() if v else None


def _multipart_body(fields: dict[str, str], file_field: str, file_path: str) -> tuple[bytes, str]:
    boundary = "----GI" + uuid.uuid4().hex
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        parts.append(f"{v}\r\n".encode())
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    fname = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        data = f.read()
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="{file_field}"; filename="{fname}"\r\n'.encode())
    parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
    parts.append(data)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def send_document(file_path: str, caption: str | None = None) -> dict[str, Any]:
    """Upload a file to Telegram via sendDocument. Returns dict with ok/message_id/file_id."""
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "error": "missing credentials"}
    if not os.path.exists(file_path):
        return {"ok": False, "error": "file not found"}
    size = os.path.getsize(file_path)
    if size > MAX_FILE_BYTES:
        return {"ok": False, "error": f"file too large ({size} > {MAX_FILE_BYTES})"}
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption[:1024]
    body, boundary = _multipart_body(fields, "document", file_path)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            d = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read())
        except Exception:
            return {"ok": False, "error": f"http {e.code}"}
    if not d.get("ok"):
        return {"ok": False, "error": d.get("description", "telegram error")}
    res = d.get("result", {})
    doc = res.get("document", {})
    return {
        "ok": True,
        "message_id": res.get("message_id"),
        "file_id": doc.get("file_id"),
        "file_unique_id": doc.get("file_unique_id"),
        "file_size": doc.get("file_size"),
    }


def download_file(file_id: str, out_path: str) -> dict[str, Any]:
    """Download a file by file_id. Returns ok + sha256."""
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"ok": False, "error": "missing credentials"}
    # get file path
    url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            d = json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(type(e).__name__)}
    if not d.get("ok"):
        return {"ok": False, "error": d.get("description", "getFile failed")}
    fpath = d.get("result", {}).get("file_path")
    if not fpath:
        return {"ok": False, "error": "no file_path"}
    dl_url = f"https://api.telegram.org/file/bot{token}/{fpath}"
    try:
        with urllib.request.urlopen(dl_url, timeout=120) as resp:
            data = resp.read()
    except Exception as e:
        return {"ok": False, "error": str(type(e).__name__)}
    with open(out_path, "wb") as f:
        f.write(data)
    h = hashlib.sha256(data).hexdigest()
    return {"ok": True, "path": out_path, "sha256": h, "size": len(data)}


def send_archive_to_telegram(db: Session, archive_id: str) -> dict[str, Any]:
    row = db.get(ArchiveCatalog, archive_id) if False else None
    from domains.archive.catalog import get_archive

    row = get_archive(db, archive_id)
    if row is None:
        return {"ok": False, "error": "archive not found"}
    if not row.archive_path or not os.path.exists(row.archive_path):
        return {"ok": False, "error": "archive file missing"}
    res = send_document(row.archive_path, caption=f"GI archive {archive_id}")
    if res.get("ok"):
        row.telegram_status = "sent"
        row.telegram_message_id = str(res.get("message_id")) if res.get("message_id") is not None else None
        row.telegram_file_id = res.get("file_id")
        db.commit()
    else:
        row.telegram_status = "failed"
        db.commit()
    return res


def verify_archive_roundtrip(db: Session, archive_id: str, tmp_dir: str) -> dict[str, Any]:
    """Re-download from Telegram and verify sha256 + zip validity."""
    from domains.archive.catalog import get_archive
    from domains.archive.service import validate_archive_zip

    row = get_archive(db, archive_id)
    if row is None or not row.telegram_file_id:
        return {"ok": False, "error": "no telegram file id"}
    out_path = os.path.join(tmp_dir, f"rt_{archive_id}.zip")
    dl = download_file(row.telegram_file_id, out_path)
    if not dl.get("ok"):
        return {"ok": False, "error": dl.get("error"), "stage": "download"}
    sha_match = (dl.get("sha256") == row.sha256)
    v = validate_archive_zip(out_path)
    return {
        "ok": bool(sha_match and v.get("ok")),
        "sha_match": sha_match,
        "validation": v,
        "downloaded_sha256": dl.get("sha256"),
        "stored_sha256": row.sha256,
    }
