"""Evidence Engine (Phase 13).

مسیر: Claim → Evidence (supports/contradicts).

- برای هر Claim یک‌بار اجرا می‌شود (`evidence_extracted`).
- داده‌ی نامزد: متن مقالات همان Event.
- از AI برای یافتن شواهد موافق/مخالف استفاده می‌شود (structured JSON).
- وضعیت تأیید Claim از توازن شواهد به‌روزرسانی می‌شود (بند 25 و 59).
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
from backend.database.enums import EvidenceDirection, VerificationStatus
from backend.database.models.claim import Claim, Evidence
from backend.database.models.event import Event
from domains.claims.evidence_prompts import EVIDENCE_SCHEMA, EXTRACT_EVIDENCE

logger = get_logger(__name__)

MAX_EVIDENCE = 10
MAX_TEXT_CHARS = 8000


@dataclass
class EvidenceOutcome:
    claims_processed: int = 0
    evidence_created: int = 0
    supports: int = 0
    contradicts: int = 0
    rejected: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "claims_processed": self.claims_processed,
            "evidence_created": self.evidence_created,
            "supports": self.supports,
            "contradicts": self.contradicts,
            "rejected": self.rejected,
            "failed": self.failed,
            "errors": self.errors,
        }


@dataclass
class CollectResult:
    """نتیجهی پردازش یک Claim: شواهد ساختهشده + تعداد موارد ردشده."""

    created: list[Evidence] = field(default_factory=list)
    rejected: int = 0


def _clamp01(value: object, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def verify_status(supports: int, contradicts: int) -> str:
    """وضعیت تأیید را از توازن شواهد تعیین می‌کند (deterministic)."""
    if supports == 0 and contradicts == 0:
        return VerificationStatus.unverified.value
    if supports > 0 and contradicts > 0:
        return VerificationStatus.disputed.value
    if supports >= 2 and contradicts == 0:
        return VerificationStatus.corroborated.value
    if supports == 1 and contradicts == 0:
        return VerificationStatus.single_source.value
    if contradicts > 0 and supports == 0:
        return VerificationStatus.contradicted.value
    return VerificationStatus.unverified.value


class EvidenceEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    def _candidate_text(self, claim: Claim) -> str:
        parts = []
        event: Event | None = claim.event
        if event is not None:
            if event.action:
                parts.append(event.action)
            for article in event.articles[:8]:
                if article.title:
                    parts.append(article.title)
                if article.summary:
                    parts.append(article.summary)
        return "\n".join(parts)[:MAX_TEXT_CHARS]

    async def collect_for_claim(self, claim: Claim) -> CollectResult:
        claim_text = f"{claim.subject} {claim.predicate} {claim.object or ''}".strip()
        data = self._candidate_text(claim)

        items: list[dict] = []
        used_ai = False
        if data.strip():
            try:
                prompt = EXTRACT_EVIDENCE.render(
                    claim=claim_text, data=data, max_items=MAX_EVIDENCE
                )
                request = AIRequest(
                    messages=[
                        Message.system("You output strict JSON compatible with the schema."),
                        Message.user(prompt),
                    ],
                    role="critic",
                    task="extract_evidence",
                    temperature=0.1,
                    json_schema=EVIDENCE_SCHEMA,
                    metadata={"prompt_version": EXTRACT_EVIDENCE.version},
                )
                response = await self.gateway.structured_generate(request, EVIDENCE_SCHEMA)
                if response.is_mock and not self._settings.mock_mode:
                    raise ValueError("mock evidence rejected in production mode")
                parsed = response.structured or _safe_json(response.text) or {}
                items = parsed.get("evidence") or []
                used_ai = bool(items)
            except Exception as exc:  # noqa: BLE001
                logger.warning("evidence collection failed | claim=%s err=%s", claim.id, exc)

        result = self._ingest_items(claim, items)

        claim.evidence_extracted = True
        if used_ai and claim.event is not None:
            meta = _load_meta(claim.event.event_metadata)
            meta["evidence_ai"] = True
            claim.event.event_metadata = json.dumps(meta, ensure_ascii=False)

        self.db.flush()
        return result

    def _ingest_items(self, claim: Claim, items: list) -> CollectResult:
        """پردازش پاسخ AI: ساخت Evidence از موارد معتبر + شمارش موارد ردشده."""
        created: list[Evidence] = []
        rejected = 0
        document_id = self._claim_document_id(claim)
        source_id = self._claim_source_id(claim)
        for item in list(items)[:MAX_EVIDENCE]:
            if not isinstance(item, dict):
                rejected += 1
                continue
            direction = str(item.get("direction") or "").lower()
            if direction not in (
                EvidenceDirection.supports.value,
                EvidenceDirection.contradicts.value,
            ):
                rejected += 1
                logger.warning(
                    "evidence rejected | claim=%s direction=%r", claim.id, direction
                )
                continue
            ev = Evidence(
                claim_id=claim.id,
                direction=direction,
                summary=(str(item.get("summary") or "").strip() or None),
                source_id=source_id,
                document_id=document_id,
                weight=_clamp01(item.get("weight"), 0.5),
                confidence=_clamp01(item.get("confidence"), 0.5),
            )
            self.db.add(ev)
            created.append(ev)
        self.db.flush()
        return CollectResult(created=created, rejected=rejected)

    def _claim_document_id(self, claim: Claim):
        event = claim.event
        if event is not None and event.articles:
            return event.articles[0].document_id
        return None

    def _claim_source_id(self, claim: Claim):
        """منبع سندِ مبنا برای Evidence (برای Source Independence در Phase 14)."""
        event = claim.event
        if event is not None and event.articles:
            document = event.articles[0].document
            if document is not None:
                return document.source_id
        return None

    def _refresh_status(self, claim: Claim) -> None:
        supports = sum(1 for e in claim.evidence if e.direction == "supports")
        contradicts = sum(1 for e in claim.evidence if e.direction == "contradicts")
        claim.verification_status = verify_status(supports, contradicts)

    async def run(self, *, limit: int = 50) -> EvidenceOutcome:
        stmt = (
            select(Claim)
            .where(Claim.evidence_extracted.is_(False))
            .order_by(Claim.created_at.desc())
            .limit(limit)
        )
        claims = list(self.db.execute(stmt).scalars().all())
        outcome = EvidenceOutcome()
        for claim in claims:
            try:
                result = await self.collect_for_claim(claim)
                self.db.refresh(claim)
                self._refresh_status(claim)
                outcome.claims_processed += 1
                outcome.evidence_created += len(result.created)
                outcome.rejected += result.rejected
                for ev in result.created:
                    if ev.direction == "supports":
                        outcome.supports += 1
                    else:
                        outcome.contradicts += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("evidence claim failed | claim=%s err=%s", claim.id, exc)
            self.db.commit()
        logger.info("evidence engine done | %s", outcome.as_dict())
        return outcome


def _load_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


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
