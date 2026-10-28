"""Settings API — مدیریت Provider/Model/Agent/بودجه از رابط (Step 8).

امنیت:
- پشت احراز هویت (main.py: protected).
- کلید فقط write-only؛ پاسخ فقط key_set/key_hint.
- تست اتصال: محدودیت ۱۰/دقیقه برای هر IP + خطای ساده‌شده (بدون جزئیات حساس).
- هر تغییر: bump نسخه‌ی Gateway (reload بدون ری‌استارت).
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime

from domains.audit.service import log_action
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai import credentials_store as store
from backend.ai.credentials import (
    CredentialError,
    decrypt_secret,
    encrypt_secret,
    last4_of,
    mask_secret,
    validate_base_url,
)
from backend.api.errors import DEFAULT_MESSAGE, SAFE_MESSAGES
from backend.api.schemas.settings import (
    AppSettingsUpdate,
    AssignmentItem,
    AssignmentRead,
    DiversityRead,
    ImportEnvResponse,
    KeyRotateRequest,
    ModelBlockRequest,
    ModelCreate,
    ModelRead,
    ModelUpdate,
    ModelVerifyRequest,
    ProviderCreate,
    ProviderRead,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderUpdate,
    VoidRequest,
)
from backend.database.models.ai_settings import (
    PROVIDER_KINDS,
    AgentAssignment,
    AIModelRow,
    AIProviderRow,
)
from backend.database.session import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

# نگاشت agentهای معتبر debate (قرارداد v1)
VALID_AGENTS = ("bull", "bear", "macro", "geopolitical", "risk_critic", "report")

# سقف تست اتصال: ۱۰ در دقیقه برای هر IP
_TEST_HITS: dict[str, list[float]] = defaultdict(list)
TEST_LIMIT_PER_MIN = 10
# cache کوتاه لیست مدل‌ها (۶۰ ثانیه)
_MODEL_CACHE: dict[str, tuple[float, list[str]]] = {}


def _test_allowed(client_ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _TEST_HITS[client_ip] if t > now - 60.0]
    _TEST_HITS[client_ip] = hits
    if len(hits) >= TEST_LIMIT_PER_MIN:
        return False
    hits.append(now)
    _TEST_HITS[client_ip] = hits
    return True


def _to_provider_read(p: AIProviderRow) -> ProviderRead:
    return ProviderRead(
        id=str(p.id), name=p.name, kind=p.kind, base_url=p.base_url,
        key_set=bool(p.api_key_encrypted),
        key_hint=p.key_hint or mask_secret(False),
        key_source="db",
        enabled=bool(p.enabled),
        last_test_status=p.last_test_status,
        last_tested_at=p.last_tested_at.isoformat() if p.last_tested_at else None,
    )


def _to_env_read(info: dict) -> ProviderRead:
    return ProviderRead(
        id=f"env:{info['kind']}", name=info["name"], kind=info["kind"],
        base_url=info.get("base_url"), key_set=True, key_hint="از .env",
        key_source="env", enabled=True,
        last_test_status=None, last_tested_at=None,
    )


def _get_provider(db: Session, provider_id: uuid.UUID) -> AIProviderRow:
    row = db.get(AIProviderRow, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="provider not found")
    return row


def _resolve_target(db: Session, provider_id: str) -> tuple[str, AIProviderRow | None]:
    """id می‌تواند UUID ردیف DB یا 'env:{kind}' (فقط‌خواندنی) باشد. خروجی: (kind, row?)."""
    if provider_id.startswith("env:"):
        kind = provider_id[4:]
        if kind not in [i["kind"] for i in store.list_env_providers()]:
            raise HTTPException(status_code=404, detail="provider not found")
        return kind, None
    try:
        uid = uuid.UUID(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bad provider id") from exc
    row = _get_provider(db, uid)
    return row.kind, row


def _require_db_row(row: AIProviderRow | None, action: str) -> AIProviderRow:
    if row is None:
        raise HTTPException(
            status_code=422,
            detail=f"{action} برای ارائه‌دهنده‌ی .env ممکن نیست؛ در .env مدیریت می‌شود یا اول «انتقال به DB» بزنید",
        )
    return row


def _check_kind(kind: str) -> None:
    if kind not in PROVIDER_KINDS or kind == "mock":
        raise HTTPException(
            status_code=422, detail=f"kind must be one of {[k for k in PROVIDER_KINDS if k != 'mock']}")


# ---------- providers ----------
@router.get("/providers", response_model=list[ProviderRead])
def list_providers(db: Session = Depends(get_db)) -> list[ProviderRead]:
    rows = db.execute(select(AIProviderRow).order_by(AIProviderRow.name)).scalars().all()
    out = [_to_provider_read(r) for r in rows]
    db_kinds = {r.kind for r in rows}
    # ارائه‌دهندگان .env که هنوز به DB منتقل نشده‌اند (فقط‌خواندنی)
    for info in store.list_env_providers():
        if info["kind"] not in db_kinds:
            out.append(_to_env_read(info))
    return out


@router.post("/providers", response_model=ProviderRead)
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)) -> ProviderRead:
    _check_kind(payload.kind)
    exists = db.execute(
        select(AIProviderRow).where(AIProviderRow.name == payload.name.strip())
    ).scalars().first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="provider name already exists")
    base_url = None
    if payload.kind == "openai_compatible":
        if not payload.base_url:
            raise HTTPException(status_code=422, detail="base_url is required for custom kind")
        try:
            base_url = validate_base_url(payload.base_url)
        except CredentialError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif payload.base_url:
        raise HTTPException(status_code=422, detail="base_url only allowed for openai_compatible")
    if payload.kind == "cloudflare" and not (payload.extra or {}).get("account_id"):
        raise HTTPException(status_code=422, detail="cloudflare requires extra.account_id")
    enc_key = enc_extra = hint = None
    if payload.api_key:
        try:
            enc_key = encrypt_secret(payload.api_key)
        except CredentialError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        hint = mask_secret(True, last4_of(payload.api_key))
    if payload.extra:
        try:
            enc_extra = encrypt_secret(json.dumps(payload.extra, ensure_ascii=False))
        except CredentialError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = AIProviderRow(
        name=payload.name.strip(), kind=payload.kind, base_url=base_url,
        api_key_encrypted=enc_key, key_hint=hint, extra_encrypted=enc_extra,
        enabled=payload.enabled,
    )
    db.add(row)
    db.flush()
    if payload.default_model and payload.default_model.strip():
        db.add(AIModelRow(provider_id=row.id,
                          model_name=payload.default_model.strip(), enabled=True))
    db.commit()
    db.refresh(row)
    store.bump_version()
    log_action(db, action="provider_create", actor="settings",
               target_type="ai_provider", target_id=str(row.id),
               params={"name": row.name, "kind": row.kind}, result={"ok": True})
    return _to_provider_read(row)


@router.put("/providers/{provider_id}", response_model=ProviderRead)
def update_provider(provider_id: str, payload: ProviderUpdate,
                    db: Session = Depends(get_db)) -> ProviderRead:
    _kind, row = _resolve_target(db, provider_id)
    row = _require_db_row(row, "ویرایش")
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.base_url is not None:
        if row.kind != "openai_compatible":
            raise HTTPException(status_code=422, detail="base_url only for openai_compatible")
        try:
            row.base_url = validate_base_url(payload.base_url)
        except CredentialError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.api_key is not None:
        try:
            row.api_key_encrypted = encrypt_secret(payload.api_key)
        except CredentialError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.key_hint = mask_secret(True, last4_of(payload.api_key))
    if payload.extra is not None:
        try:
            row.extra_encrypted = encrypt_secret(json.dumps(payload.extra, ensure_ascii=False))
        except CredentialError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    store.bump_version()
    return _to_provider_read(row)


@router.post("/providers/{provider_id}/key", response_model=ProviderRead)
def rotate_key(provider_id: str, payload: KeyRotateRequest,
               db: Session = Depends(get_db)) -> ProviderRead:
    _kind, row = _resolve_target(db, provider_id)
    row = _require_db_row(row, "تغییر کلید")
    try:
        row.api_key_encrypted = encrypt_secret(payload.api_key)
    except CredentialError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row.key_hint = mask_secret(True, last4_of(payload.api_key))
    db.commit()
    db.refresh(row)
    store.bump_version()
    log_action(db, action="provider_key_rotate", actor="settings",
               target_type="ai_provider", target_id=str(row.id),
               params={"name": row.name}, result={"ok": True})
    return _to_provider_read(row)


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: str, db: Session = Depends(get_db)) -> dict:
    _kind, row = _resolve_target(db, provider_id)
    row = _require_db_row(row, "حذف")
    used_agents = db.execute(
        select(AgentAssignment).where(
            AgentAssignment.provider_id == row.id, AgentAssignment.enabled.is_(True))
    ).scalars().all()
    models = db.execute(
        select(AIModelRow).where(AIModelRow.provider_id == row.id)
    ).scalars().all()
    blockers = []
    if used_agents:
        blockers.append("agents: " + ", ".join(a.agent for a in used_agents))
    if models:
        blockers.append(f"{len(models)} model(s)")
    if blockers:
        raise HTTPException(
            status_code=409,
            detail="provider in use; remap or remove first: " + "; ".join(blockers),
        )
    db.delete(row)
    db.commit()
    store.bump_version()
    log_action(db, action="provider_delete", actor="settings",
               target_type="ai_provider", target_id=str(provider_id),
               params={"name": row.name}, result={"ok": True})
    return {"ok": True}


@router.post("/providers/{provider_id}/test", response_model=ProviderTestResponse)
def test_provider(provider_id: str, payload: ProviderTestRequest,
                  request: Request, db: Session = Depends(get_db)) -> ProviderTestResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _test_allowed(client_ip):
        raise HTTPException(status_code=429, detail="too many connection tests; retry in a minute")
    kind, row = _resolve_target(db, provider_id)
    if row is not None and not row.enabled:
        raise HTTPException(status_code=422, detail="provider is disabled")
    if row is not None and not row.api_key_encrypted:
        raise HTTPException(status_code=422, detail="no API key stored for this provider")
    label = row.name if row is not None else kind
    started = time.perf_counter()
    try:
        from backend.ai.gateway import AIGateway
        from backend.ai.schemas.types import AIRequest, Message

        gateway = AIGateway()
        # تست اتصال: دقیقاً یک تلاش صریح، بدون retry/fallback پنهان.
        gateway._max_retries = 0
        resp = asyncio.run(gateway.generate(AIRequest(
            messages=[Message.user("Reply with exactly: OK")],
            task="connectivity_check", temperature=0.0, max_tokens=32,
            metadata={"force_provider": row.name if row is not None else kind,
                      **({"model": payload.model} if payload.model else {})},
        )))
        ok = not resp.is_mock
        if row is not None:
            row.last_test_status = "ok" if ok else "fail"
            row.last_tested_at = datetime.now(UTC)
            db.commit()
        return ProviderTestResponse(
            ok=ok, provider=label, model=resp.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            error=None if ok else "mock response (check MOCK_MODE)",
        )
    except Exception as exc:  # noqa: BLE001
        simple = SAFE_MESSAGES.get(getattr(exc, "kind", None), DEFAULT_MESSAGE)
        try:
            if row is not None:
                row.last_test_status = "fail"
                row.last_tested_at = datetime.now(UTC)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
        return ProviderTestResponse(ok=False, provider=label, error=simple)


@router.get("/providers/{provider_id}/models", response_model=list[str])
def discover_models(provider_id: str, db: Session = Depends(get_db)) -> list[str]:
    kind, row = _resolve_target(db, provider_id)
    if row is not None:
        if row.kind not in ("groq", "openrouter", "openai", "gemini", "openai_compatible"):
            return []
        cache_key = str(row.id)
        base = row.base_url
        api_key: str | None = None
        if row.api_key_encrypted:
            try:
                api_key = decrypt_secret(row.api_key_encrypted)
            except CredentialError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        if kind not in ("groq", "openrouter", "openai", "gemini"):
            return []
        cache_key = f"env:{kind}"
        base = None
        from backend.ai.credentials_store import ENV_PROVIDER_FIELDS
        from backend.core.config import get_settings

        settings = get_settings()
        key_attr = ENV_PROVIDER_FIELDS[kind][0]
        api_key = getattr(settings, key_attr, None)
        base = getattr(settings, ENV_PROVIDER_FIELDS[kind][1], None) if ENV_PROVIDER_FIELDS[kind][1] else None
    cached = _MODEL_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < 60.0:
        return cached[1]
    if not api_key:
        raise HTTPException(status_code=422, detail="no API key stored for this provider")
    headers = {"Content-Type": "application/json"}
    if kind == "gemini":
        headers["x-goog-api-key"] = api_key
        url: str | None = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=50"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        base = base or {
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "openai": "https://api.openai.com/v1",
        }.get(kind, "")
        if not base:
            return []
        url = f"{base.rstrip('/')}/models"
    # Send-time revalidation: a stored custom URL may have gone stale since
    # it was saved; fail closed here before any credential leaves the server.
    try:
        from backend.ai.credentials import validate_base_url
        validate_base_url(url)
    except CredentialError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    import httpx

    from backend.ai.providers import http_base as _httpbase

    try:
        # No env proxy/CA trust, no redirects; bounded body. Same guarantees
        # as the GuardedTransport model path, adapted to this sync endpoint.
        with httpx.Client(timeout=20.0, follow_redirects=False,
                          trust_env=False) as client:
            req = client.build_request("GET", url, headers=headers)
            resp = client.send(req, stream=True)
            raw = _httpbase.read_limited_body_sync(
                resp, _httpbase.DISCOVER_MAX_RESPONSE_BYTES)
            resp.raise_for_status()
            data = json.loads(raw)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="could not fetch model list") from exc
    names: list[str] = []
    if kind == "gemini":
        names = [str(m.get("name", "")).replace("models/", "")
                 for m in (data.get("models") or []) if m.get("name")]
    else:
        names = [str(m.get("id", "")) for m in (data.get("data") or []) if m.get("id")]
    _MODEL_CACHE[cache_key] = (time.monotonic(), names)
    return names


# ---------- models ----------
def _to_model_read(m: AIModelRow, provider_name: str) -> ModelRead:
    from backend.ai import free_policy as _policy

    review_after = _policy.review_after(m)
    verified_on = getattr(m, "free_verified_on", None)
    return ModelRead(
        id=str(m.id), provider_id=str(m.provider_id), provider_name=provider_name,
        model_name=m.model_name, price_in_per_mtok=m.price_in_per_mtok,
        price_out_per_mtok=m.price_out_per_mtok, enabled=bool(m.enabled),
        free_status=_policy.effective_free_status(m),
        free_source_url=getattr(m, "free_source_url", None),
        free_verified_on=verified_on.isoformat() if verified_on else None,
        free_review_after=review_after.isoformat() if review_after else None,
        free_limits=getattr(m, "free_limits", None),
        free_account_prereqs=getattr(m, "free_account_prereqs", None),
        free_privacy_notes=getattr(m, "free_privacy_notes", None),
        free_verified_by=getattr(m, "free_verified_by", None),
        free_blocked_reason=getattr(m, "free_blocked_reason", None),
    )


def _require_verified_fresh(m: AIModelRow, action: str) -> None:
    """Activation gate: only fresh FREE_VERIFIED models may be enabled."""
    from backend.ai import free_policy as _policy

    status = _policy.effective_free_status(m)
    if status != _policy.FREE_VERIFIED:
        hints = {
            _policy.UNVERIFIED: "verify first via POST /models/{id}/verify",
            _policy.REVIEW_REQUIRED: "review expired; re-verify to continue",
            _policy.BLOCKED: f"blocked: {getattr(m, 'free_blocked_reason', None) or 'no reason'}",
        }
        raise HTTPException(
            status_code=422,
            detail=f"cannot {action}: model is {status} ({hints.get(status, '')})")


@router.get("/models", response_model=list[ModelRead])
def list_models(db: Session = Depends(get_db)) -> list[ModelRead]:
    rows = db.execute(
        select(AIModelRow, AIProviderRow.name)
        .join(AIProviderRow, AIModelRow.provider_id == AIProviderRow.id)
        .order_by(AIProviderRow.name, AIModelRow.model_name)
    ).all()
    return [_to_model_read(m, n) for m, n in rows]


@router.post("/models", response_model=ModelRead)
def create_model(payload: ModelCreate, db: Session = Depends(get_db)) -> ModelRead:
    if payload.provider_id.startswith("env:"):
        # ارائه‌دهنده‌ی .env: ردیف پوسته (بدون کلید؛ fallback به .env) + مدل
        kind = payload.provider_id[4:]
        if kind not in [i["kind"] for i in store.list_env_providers()]:
            raise HTTPException(status_code=404, detail="provider not found")
        shell = db.execute(
            select(AIProviderRow).where(AIProviderRow.kind == kind)
        ).scalars().first()
        if shell is None:
            shell = AIProviderRow(name=kind, kind=kind, enabled=True)
            db.add(shell)
            db.flush()
        pid = shell.id
        prov_name = shell.name
    else:
        try:
            pid = uuid.UUID(payload.provider_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="bad provider_id") from exc
        prov = db.get(AIProviderRow, pid)
        if prov is None:
            raise HTTPException(status_code=404, detail="provider not found")
        prov_name = prov.name
    dup = db.execute(
        select(AIModelRow).where(AIModelRow.provider_id == pid,
                                 AIModelRow.model_name == payload.model_name.strip())
    ).scalars().first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="model already registered")
    m = AIModelRow(
        provider_id=pid, model_name=payload.model_name.strip(),
        price_in_per_mtok=payload.price_in_per_mtok,
        price_out_per_mtok=payload.price_out_per_mtok,
        # New models always start UNVERIFIED and disabled; verification is explicit.
        enabled=False, free_status="UNVERIFIED",
        free_source_url=(payload.free_source_url or "").strip() or None,
        free_limits=(payload.free_limits or "").strip() or None,
        free_account_prereqs=(payload.free_account_prereqs or "").strip() or None,
        free_privacy_notes=(payload.free_privacy_notes or "").strip() or None,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    store.bump_version()
    return _to_model_read(m, prov_name)


@router.put("/models/{model_id}", response_model=ModelRead)
def update_model(model_id: uuid.UUID, payload: ModelUpdate,
                 db: Session = Depends(get_db)) -> ModelRead:
    m = db.get(AIModelRow, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="model not found")
    if payload.model_name is not None:
        m.model_name = payload.model_name.strip()
    if payload.price_in_per_mtok is not None:
        m.price_in_per_mtok = payload.price_in_per_mtok
    if payload.price_out_per_mtok is not None:
        m.price_out_per_mtok = payload.price_out_per_mtok
    for field in ("free_source_url", "free_limits", "free_account_prereqs",
                  "free_privacy_notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(m, field, value.strip() or None)
    if payload.free_review_days is not None:
        m.free_review_days = payload.free_review_days
    if payload.enabled is not None:
        if payload.enabled:
            _require_verified_fresh(m, "enable")
        m.enabled = payload.enabled
    db.commit()
    db.refresh(m)
    store.bump_version()
    prov = db.get(AIProviderRow, m.provider_id)
    return _to_model_read(m, prov.name if prov else "")


@router.post("/models/{model_id}/verify", response_model=ModelRead)
def verify_model(model_id: uuid.UUID, payload: ModelVerifyRequest,
                 db: Session = Depends(get_db)) -> ModelRead:
    """Explicit admin verification: complete evidence + confirm required.

    Verification alone does not enable the model; enabling is a separate,
    explicit step (no auto-activation).
    """
    from backend.ai import free_policy as _policy

    m = db.get(AIModelRow, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="model not found")
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="explicit confirm=true required")
    source = (payload.source_url or getattr(m, "free_source_url", None) or "").strip()
    limits = (payload.limits if payload.limits is not None
              else getattr(m, "free_limits", None) or "").strip()
    prereqs = (payload.account_prereqs if payload.account_prereqs is not None
               else getattr(m, "free_account_prereqs", None) or "").strip()
    privacy = (payload.privacy_notes if payload.privacy_notes is not None
               else getattr(m, "free_privacy_notes", None) or "").strip()
    missing = [k for k, v in (("source_url", source), ("limits", limits),
                              ("account_prereqs", prereqs),
                              ("privacy_notes", privacy)) if not v]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"incomplete free-tier evidence: {', '.join(missing)}")
    m.free_status = _policy.FREE_VERIFIED
    m.free_source_url = source
    m.free_limits = limits
    m.free_account_prereqs = prereqs
    m.free_privacy_notes = privacy
    if payload.review_days is not None:
        m.free_review_days = payload.review_days
    m.free_verified_on = date.today()
    m.free_verified_by = "settings"
    m.free_blocked_reason = None
    db.commit()
    db.refresh(m)
    store.bump_version()
    log_action(db, action="model_verify", actor="settings",
               target_type="ai_model", target_id=str(m.id),
               params={"model": m.model_name}, result={"ok": True})
    prov = db.get(AIProviderRow, m.provider_id)
    return _to_model_read(m, prov.name if prov else "")


@router.post("/models/{model_id}/block", response_model=ModelRead)
def block_model(model_id: uuid.UUID, payload: ModelBlockRequest,
                db: Session = Depends(get_db)) -> ModelRead:
    """Block a model: disabled at once, never auto-enabled again."""
    from backend.ai import free_policy as _policy

    m = db.get(AIModelRow, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="model not found")
    m.free_status = _policy.BLOCKED
    m.free_blocked_reason = payload.reason.strip()
    m.enabled = False
    db.commit()
    db.refresh(m)
    store.bump_version()
    log_action(db, action="model_block", actor="settings",
               target_type="ai_model", target_id=str(m.id),
               params={"model": m.model_name}, result={"ok": True})
    prov = db.get(AIProviderRow, m.provider_id)
    return _to_model_read(m, prov.name if prov else "")


@router.delete("/models/{model_id}")
def delete_model(model_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    m = db.get(AIModelRow, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="model not found")
    used = db.execute(
        select(AgentAssignment).where(AgentAssignment.model_id == m.id,
                                      AgentAssignment.enabled.is_(True))
    ).scalars().all()
    if used:
        raise HTTPException(
            status_code=409,
            detail="model assigned to agents: " + ", ".join(a.agent for a in used),
        )
    db.delete(m)
    db.commit()
    store.bump_version()
    return {"ok": True}


# ---------- agents ----------
@router.get("/agent-assignments", response_model=list[AssignmentRead])
def list_assignments(db: Session = Depends(get_db)) -> list[AssignmentRead]:
    rows = db.execute(select(AgentAssignment)).scalars().all()
    out = []
    for a in rows:
        prov = db.get(AIProviderRow, a.provider_id) if a.provider_id else None
        mod = db.get(AIModelRow, a.model_id) if a.model_id else None
        out.append(AssignmentRead(
            agent=a.agent, provider_id=str(a.provider_id) if a.provider_id else None,
            provider_name=prov.name if prov else None,
            model_id=str(a.model_id) if a.model_id else None,
            model_name=mod.model_name if mod else None, enabled=bool(a.enabled)))
    return out


@router.put("/agent-assignments", response_model=list[AssignmentRead])
def put_assignments(items: list[AssignmentItem],
                    db: Session = Depends(get_db)) -> list[AssignmentRead]:
    for item in items:
        if item.agent not in VALID_AGENTS:
            raise HTTPException(status_code=422, detail=f"unknown agent: {item.agent}")
        pid = mid = None
        if item.provider_id is not None:
            try:
                pid = uuid.UUID(item.provider_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="bad provider_id") from exc
            if db.get(AIProviderRow, pid) is None:
                raise HTTPException(status_code=404, detail="provider not found")
        if item.model_id is not None:
            try:
                mid = uuid.UUID(item.model_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="bad model_id") from exc
            mod = db.get(AIModelRow, mid)
            if mod is None:
                raise HTTPException(status_code=404, detail="model not found")
            if pid is not None and mod.provider_id != pid:
                raise HTTPException(status_code=422, detail="model belongs to another provider")
        row = db.execute(
            select(AgentAssignment).where(AgentAssignment.agent == item.agent)
        ).scalars().first()
        if row is None:
            db.add(AgentAssignment(agent=item.agent, provider_id=pid,
                                   model_id=mid, enabled=item.enabled))
        else:
            row.provider_id = pid
            row.model_id = mid
            row.enabled = item.enabled
    db.commit()
    store.bump_version()
    log_action(db, action="agent_assign", actor="settings", target_type="agent_assignment",
               params={"agents": [i.agent for i in items]}, result={"ok": True})
    return list_assignments(db)


@router.get("/diversity", response_model=DiversityRead)
def diversity(db: Session = Depends(get_db)) -> DiversityRead:
    rows = db.execute(
        select(AgentAssignment).where(AgentAssignment.enabled.is_(True))
    ).scalars().all()
    models = set()
    providers = set()
    for a in rows:
        if a.model_id is not None:
            mod = db.get(AIModelRow, a.model_id)
            if mod is not None:
                models.add(mod.model_name)
                prov = db.get(AIProviderRow, mod.provider_id)
                if prov is not None:
                    providers.add(prov.kind)
        elif a.provider_id is not None:
            prov = db.get(AIProviderRow, a.provider_id)
            if prov is not None:
                providers.add(prov.kind)
    warning = None
    if rows and len(models) <= 1:
        warning = "تنوع = ۱؛ این بحث واقعی چندمدلی نیست"
    return DiversityRead(distinct_models=len(models),
                         distinct_providers=len(providers), warning=warning)


# ---------- app settings ----------
APP_KEYS = ("debate_daily_budget_usd", "debate_max_tokens_per_run",
            "debate_max_rounds", "debate_targets",
            "mock_mode", "ai_default_provider",
            "kev_local_screening_enabled", "laya_local_screening_enabled",
            "local_screening_idle_unload_seconds")


@router.get("/app")
def get_app(db: Session = Depends(get_db)) -> dict:
    from backend.database.models.ai_settings import AppSetting

    rows = db.execute(select(AppSetting)).scalars().all()
    out = {r.key: r.value for r in rows if r.key in APP_KEYS}
    defaults = {
        "kev_local_screening_enabled": "false",
        "laya_local_screening_enabled": "false",
        "local_screening_idle_unload_seconds": "300",
    }
    for k, v in defaults.items():
        out.setdefault(k, v)
    return out


@router.put("/app")
def put_app(payload: AppSettingsUpdate, db: Session = Depends(get_db)) -> dict:
    for key, value in payload.settings.items():
        if key not in APP_KEYS:
            raise HTTPException(status_code=422, detail=f"unknown setting: {key}")
        if key == "mock_mode" and value.strip().lower() not in (
                "1", "true", "yes", "on", "0", "false", "no", "off"):
            raise HTTPException(status_code=422, detail="mock_mode must be true/false")
        if key == "ai_default_provider" and not value.strip():
            raise HTTPException(status_code=422, detail="ai_default_provider is required")
        if key in ("kev_local_screening_enabled", "laya_local_screening_enabled") and \
                value.strip().lower() not in ("1", "true", "yes", "on", "0", "false", "no", "off"):
            raise HTTPException(status_code=422, detail=f"{key} must be true/false")
        if key == "local_screening_idle_unload_seconds":
            try:
                n = int(value.strip())
            except ValueError:
                raise HTTPException(status_code=422, detail="idle_unload_seconds must be an integer") from None
            if n < 0 or n > 86400:
                raise HTTPException(status_code=422, detail="idle_unload_seconds out of range")
        try:
            store.set_app_setting(db, key, value)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    store.bump_version()
    log_action(db, action="app_settings_update", actor="settings",
               target_type="app_setting",
               params={"keys": sorted(payload.settings)},
               result={"ok": True})
    return get_app(db)


# ---------- import from .env ----------
ENV_PROVIDER_VARS = {
    "gemini": ("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_MODEL"),
    "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_BASE_URL", "OPENROUTER_MODEL"),
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"),
    "groq": ("GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_MODEL"),
    "cloudflare": ("CLOUDFLARE_API_TOKEN", None, None),
}


@router.post("/import-from-env", response_model=ImportEnvResponse)
def import_from_env(db: Session = Depends(get_db)) -> ImportEnvResponse:
    from backend.core.config import get_settings

    settings = get_settings()
    if not (settings.app_encryption_key or "").strip():
        return ImportEnvResponse(moved=[], skipped=list(ENV_PROVIDER_VARS),
                                 needs_encryption_key=True)
    moved, skipped = [], []
    for kind, (key_var, _base_var, model_var) in ENV_PROVIDER_VARS.items():
        api_key = getattr(settings, key_var.lower(), None)
        if not api_key:
            skipped.append(kind)
            continue
        exists = db.execute(
            select(AIProviderRow).where(AIProviderRow.kind == kind)
        ).scalars().first()
        if exists is not None and exists.api_key_encrypted:
            skipped.append(kind)
            continue
        try:
            enc = encrypt_secret(api_key)
        except CredentialError:
            skipped.append(kind)
            continue
        model_name = getattr(settings, model_var.lower(), None) if model_var else None
        if kind == "cloudflare":
            # مدل پیش‌فرض زنده‌تست‌شده ثبت می‌شود (بدون قیمت).
            model_name = "@cf/meta/llama-3.1-8b-instruct"
        if exists is None:
            row = AIProviderRow(name=kind, kind=kind, api_key_encrypted=enc,
                                key_hint=mask_secret(True, last4_of(api_key)),
                                enabled=True)
            db.add(row)
            db.flush()
        else:
            row = exists
            row.api_key_encrypted = enc
            row.key_hint = mask_secret(True, last4_of(api_key))
        if kind == "cloudflare":
            # Account ID هم منتقل می‌شود (وگرنه Provider ناقص می‌ماند).
            account_id = getattr(settings, "cloudflare_account_id", None)
            if account_id:
                try:
                    row.extra_encrypted = encrypt_secret(
                        json.dumps({"account_id": account_id}, ensure_ascii=False))
                except CredentialError:
                    pass
        if model_name:
            dup = db.execute(
                select(AIModelRow).where(AIModelRow.provider_id == row.id,
                                         AIModelRow.model_name == model_name)
            ).scalars().first()
            if dup is None:
                db.add(AIModelRow(provider_id=row.id, model_name=model_name,
                                  enabled=True))
        moved.append(kind)
    db.commit()
    if moved:
        store.bump_version()
        log_action(db, action="import_env_keys", actor="settings",
                   target_type="ai_provider", params={"moved": moved},
                   result={"ok": True})
    return ImportEnvResponse(moved=moved, skipped=skipped)


# ---------- void (به‌جای حذف) ----------
@router.post("/debate-runs/{run_id}/void")
def void_debate_run(run_id: uuid.UUID, payload: VoidRequest,
                    db: Session = Depends(get_db)) -> dict:
    from backend.database.models.debate import DebateRun

    run = db.get(DebateRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="debate run not found")
    run.status = "void"
    run.void_reason = payload.reason[:1000]
    db.commit()
    log_action(db, action="debate_void", actor="settings", target_type="debate_run",
               target_id=str(run_id), params={"reason": payload.reason[:200]},
               result={"ok": True})
    return {"ok": True}


@router.post("/forecasts/{forecast_id}/void")
def void_forecast(forecast_id: uuid.UUID, payload: VoidRequest,
                  db: Session = Depends(get_db)) -> dict:
    from backend.database.models.forecast import Forecast

    fc = db.get(Forecast, forecast_id)
    if fc is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    fc.status = "void"
    fc.void_reason = payload.reason[:1000]
    db.commit()
    log_action(db, action="forecast_void", actor="settings", target_type="forecast",
               target_id=str(forecast_id), params={"reason": payload.reason[:200]},
               result={"ok": True})
    return {"ok": True}


@router.get("/spend-today")
def spend_today(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import func

    from backend.database.models.debate import DebateMessage

    tokens = db.execute(
        select(func.coalesce(func.sum(DebateMessage.total_tokens), 0)).where(
            func.date(DebateMessage.created_at) == func.current_date())
    ).scalars().one()
    usd = db.execute(
        select(func.coalesce(func.sum(DebateMessage.cost_estimate), 0.0)).where(
            func.date(DebateMessage.created_at) == func.current_date())
    ).scalars().one()
    return {"tokens_today": int(tokens or 0), "usd_today": round(float(usd or 0.0), 6)}
