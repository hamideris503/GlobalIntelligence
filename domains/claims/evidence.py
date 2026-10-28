"""Evidence Engine (Phase 13).

مسیر: Claim → Evidence (supports/contradicts).

- برای هر Claim حداکثر ۵ بار تلاش می‌شود (`evidence_attempts`؛ Step 6).
- داده‌ی نامزد: متن مقالات همان Event.
- از AI برای یافتن شواهد موافق/مخالف استفاده می‌شود (structured JSON).
- وضعیت تأیید Claim از توازن شواهد به‌روزرسانی می‌شود (بند 25 و 59).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.mock_mode import effective_mock_mode
from backend.database.enums import EvidenceDirection, VerificationStatus
from backend.database.models.claim import Claim, Evidence
from backend.database.models.event import Event
from domains.claims.evidence_prompts import EVIDENCE_SCHEMA, EXTRACT_EVIDENCE

logger = get_logger(__name__)

MAX_EVIDENCE = 10
MAX_TEXT_CHARS = 8000
# سقف تلاش شواهد برای هر Claim (Step 6؛ خرابی دائمی retry بی‌نهایت نمی‌شود)
MAX_EVIDENCE_ATTEMPTS = 5

# Serialize in-process with the n8n /api/claims/evidence caller.
_RUN_LOCK = asyncio.Lock()


@dataclass
class EvidenceOutcome:
    claims_processed: int = 0
    evidence_created: int = 0
    supports: int = 0
    contradicts: int = 0
    rejected: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "claims_processed": self.claims_processed,
            "evidence_created": self.evidence_created,
            "supports": self.supports,
            "contradicts": self.contradicts,
            "rejected": self.rejected,
            "failed": self.failed,
            "skipped": self.skipped,
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
        # AUDIT-REPAIR: مقالات شماره‌دار تا article_index معنادار باشد
        parts = []
        event: Event | None = claim.event
        if event is not None:
            if event.action:
                parts.append(event.action)
            for idx, article in enumerate(event.articles[:8]):
                block = f"[{idx}] {article.title or ''}\n{article.summary or ''}".strip()
                if block != f"[{idx}]":
                    parts.append(block)
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
                if response.is_mock and not effective_mock_mode():
                    raise ValueError("mock evidence rejected in production mode")
                parsed = response.structured or _safe_json(response.text) or {}
                # E2E FIND: بعضی مدل‌ها آرایه‌ی تاپ‌لول می‌دهند، نه آبجکت؛ بردبار باش
                if isinstance(parsed, list):
                    items = parsed
                else:
                    items = parsed.get("evidence") or []
                used_ai = bool(items)
            except Exception as exc:  # noqa: BLE001
                # AUDIT-REPAIR: شکست AI دیگر done جعلی نمی‌سازد؛ خطا بالا می‌رود
                # تا run() آن را failed بشمارد و در اجرای بعد retry شود.
                logger.warning("evidence collection failed | claim=%s err=%s", claim.id, exc)
                raise

        result = self._ingest_items(claim, items)

        claim.evidence_extracted = True
        if used_ai and claim.event is not None:
            meta = _load_meta(claim.event.event_metadata)
            meta["evidence_ai"] = True
            claim.event.event_metadata = json.dumps(meta, ensure_ascii=False)

        self.db.flush()
        return result

    def _ingest_items(self, claim: Claim, items: list) -> CollectResult:
        """پردازش پاسخ AI: ساخت Evidence از موارد معتبر + شمارش موارد ردشده.

        AUDIT-REPAIR: هر شاهد به مقاله‌ی ارجاع‌شده (article_index) منتسب می‌شود؛
        اندیس نامعتبر/تهی → مقاله‌ی اول (fallback مستند).
        """
        created: list[Evidence] = []
        rejected = 0
        articles = list(claim.event.articles[:8]) if claim.event is not None else []
        # IDEMPOTENCY (E2E): همان شاهد برای یک claim دوباره ساخته نمی‌شود
        seen = {(e.direction, e.summary, e.weight)
                for e in self.db.execute(
                    select(Evidence).where(Evidence.claim_id == claim.id)
                ).scalars().all()}
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
            try:
                index = int(item.get("article_index"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                index = 0
            if not 0 <= index < max(1, len(articles)):
                logger.warning(
                    "evidence article_index out of range | claim=%s index=%r",
                    claim.id, item.get("article_index"),
                )
                index = 0
            document_id, source_id = None, None
            if articles:
                target = articles[index]
                document_id = target.document_id
                document = target.document
                if document is not None:
                    source_id = document.source_id
            summary = (str(item.get("summary") or "").strip() or None)
            weight = _clamp01(item.get("weight"), 0.5)
            if (direction, summary, weight) in seen:
                rejected += 1
                logger.warning("evidence duplicate skipped | claim=%s", claim.id)
                continue
            seen.add((direction, summary, weight))
            ev = Evidence(
                claim_id=claim.id,
                direction=direction,
                summary=summary,
                source_id=source_id,
                document_id=document_id,
                weight=weight,
                confidence=_clamp01(item.get("confidence"), 0.5),
            )
            self.db.add(ev)
            created.append(ev)
        self.db.flush()
        return CollectResult(created=created, rejected=rejected)

    def _refresh_status(self, claim: Claim) -> None:
        supports = sum(1 for e in claim.evidence if e.direction == "supports")
        contradicts = sum(1 for e in claim.evidence if e.direction == "contradicts")
        claim.verification_status = verify_status(supports, contradicts)

    async def run(self, *, limit: int = 50,
                  claim_ids: list | None = None) -> EvidenceOutcome:
        async with _RUN_LOCK:
            return await self._run(limit=limit, claim_ids=claim_ids)

    async def _run(self, *, limit: int = 50,
                   claim_ids: list | None = None) -> EvidenceOutcome:
        stmt = (
            select(Claim)
            .where(
                Claim.evidence_extracted.is_(False),
                Claim.evidence_attempts < MAX_EVIDENCE_ATTEMPTS,
            )
            .order_by(Claim.created_at.desc())
            .limit(limit)
        )
        if claim_ids:
            stmt = stmt.where(Claim.id.in_(list(claim_ids)))
        claims = list(self.db.execute(stmt).scalars().all())
        outcome = EvidenceOutcome()
        # Production guard BEFORE the attempts counter: claims on mock-linked
        # events are skipped without burning attempts or creating evidence.
        mock_events: set = set()
        if not effective_mock_mode() and claims:
            from backend.database.models.document import events_with_mock_articles

            mock_events = events_with_mock_articles(
                self.db, [c.event_id for c in claims]
            )
        for claim in claims:
            if claim.event_id in mock_events:
                outcome.skipped += 1
                continue
            claim.evidence_attempts = (claim.evidence_attempts or 0) + 1
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
