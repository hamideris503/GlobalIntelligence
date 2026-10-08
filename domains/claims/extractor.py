"""Claim Extraction (Phase 12).

مسیر: Event (یا Article) → Claims (subject-predicate-object).

- برای هر Event یک‌بار اجرا می‌شود (`claims_extracted`).
- از متن مقالات همان رویداد، Claims اتمی استخراج می‌شود (structured JSON).
- در نبود AI، از خود Event یک Claim پایه ساخته می‌شود (fallback).
- Evidence (موافق/مخالف) در Phase 13 اضافه می‌شود؛ اینجا فقط Claimهای اولیه.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.enums import VerificationStatus
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from domains.claims.prompts import CLAIMS_SCHEMA, EXTRACT_CLAIMS

logger = get_logger(__name__)

MAX_CLAIMS = 8
MAX_TEXT_CHARS = 6000


@dataclass
class ClaimOutcome:
    events_processed: int = 0
    claims_created: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "events_processed": self.events_processed,
            "claims_created": self.claims_created,
            "failed": self.failed,
            "errors": self.errors,
        }


def _clamp01(value: object, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


class ClaimExtractor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    def _event_text(self, event: Event) -> str:
        parts = []
        if event.action:
            parts.append(event.action)
        for article in event.articles[:8]:
            if article.title:
                parts.append(article.title)
            if article.summary:
                parts.append(article.summary)
        return "\n".join(parts)[:MAX_TEXT_CHARS]

    async def extract_for_event(self, event: Event) -> list[Claim]:
        text = self._event_text(event)
        claims_data: list[dict] = []
        used_ai = False

        if text.strip():
            try:
                prompt = EXTRACT_CLAIMS.render(data=text, max_claims=MAX_CLAIMS)
                request = AIRequest(
                    messages=[
                        Message.system("You output strict JSON compatible with the schema."),
                        Message.user(prompt),
                    ],
                    role="deep_analysis",
                    task="extract_claims",
                    temperature=0.1,
                    json_schema=CLAIMS_SCHEMA,
                    metadata={"prompt_version": EXTRACT_CLAIMS.version},
                )
                response = await self.gateway.structured_generate(request, CLAIMS_SCHEMA)
                if response.is_mock and not self._settings.mock_mode:
                    raise ValueError("mock claims rejected in production mode")
                data = response.structured or _safe_json(response.text) or {}
                claims_data = data.get("claims") or []
                used_ai = bool(claims_data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("claim extraction failed, fallback | err=%s", exc)

        # fallback: یک Claim پایه از خود Event
        if not claims_data and event.action:
            claims_data = [
                {
                    "subject": _first_actor(event) or "unknown",
                    "predicate": event.event_type or "occurred",
                    "object": event.action,
                    "claim_type": event.event_type or "unknown",
                    "confidence": event.confidence if event.confidence is not None else 0.4,
                }
            ]

        created: list[Claim] = []
        for item in claims_data[:MAX_CLAIMS]:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject") or "").strip()
            predicate = str(item.get("predicate") or "").strip()
            obj = str(item.get("object") or "").strip()
            if not (subject and predicate):
                continue
            claim = Claim(
                event_id=event.id,
                subject=subject[:512],
                predicate=predicate[:255],
                object=obj[:512] or None,
                claim_type=str(item.get("claim_type") or event.event_type or "unknown")[:64],
                claimed_at=event.occurred_at,
                sources=event.sources,
                confidence=_clamp01(item.get("confidence"), event.confidence or 0.5),
                verification_status=VerificationStatus.unverified.value,
            )
            self.db.add(claim)
            created.append(claim)

        event.claims_extracted = True
        if used_ai:
            meta = {}
            if event.event_metadata:
                try:
                    meta = json.loads(event.event_metadata)
                except Exception:  # noqa: BLE001
                    meta = {}
            meta["claims_ai"] = True
            meta["prompt_version"] = EXTRACT_CLAIMS.version
            event.event_metadata = json.dumps(meta, ensure_ascii=False)

        self.db.flush()
        return created

    async def run(self, *, limit: int = 50) -> ClaimOutcome:
        stmt = (
            select(Event)
            .where(Event.claims_extracted.is_(False))
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        events = list(self.db.execute(stmt).scalars().all())
        outcome = ClaimOutcome()
        for event in events:
            try:
                created = await self.extract_for_event(event)
                outcome.events_processed += 1
                outcome.claims_created += len(created)
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("claim event failed | event=%s err=%s", event.id, exc)
            self.db.commit()
        logger.info("claim extraction done | %s", outcome.as_dict())
        return outcome


def _first_actor(event: Event) -> str | None:
    try:
        actors = json.loads(event.actors or "[]")
        return actors[0] if actors else None
    except Exception:  # noqa: BLE001
        return None


def _safe_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None
