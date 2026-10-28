"""Article Classification (Phase 10; اصلاحات Phase 10 fix).

- طبقه‌بندی: topics, country, language, sentiment, stance, summary, entities
- محاسبه‌ی Importance Score ترکیبی (بند 22) با ۱۰ بُعد، **deterministic**
- novelty و historical_significance از سیستم (نه LLM)
- اعتبارسنجی JSON با jsonschema
- رد کردن نتیجه‌ی mock در حالت production
- وضعیت/تلاش/خطا و متادیتای اجرا در DB (Reproducibility)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.ai.dispatch.service import DispatchService
from backend.ai.gateway import get_gateway
from backend.ai.prompts.classification import CLASSIFY_ARTICLE
from backend.ai.schemas.types import AIError, AIErrorKind, AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.mock_mode import effective_mock_mode
from backend.database.models.article import Article
from backend.database.models.document import Document
from domains.news.classifier_schema import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_TOPICS,
    CLASSIFY_SCHEMA,
    ClassificationResult,
    ImportanceInputs,
)

logger = get_logger(__name__)

MAX_ATTEMPTS = 3

# رتبه‌ی قطعی سطح برای ORDER BY صف (نامشخص/نامعتبر آخر، ولی حذف نمی‌شود)
PRIORITY_RANK: dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
UNKNOWN_RANK = len(PRIORITY_RANK)

# سطوحی که غربال اولیه را بدون AI می‌گذرانند (فقط سطح قطعی از فیلد معتبر)
LOW_PRIORITY_SKIP = ("P3", "P4")


def _pending_stmt(limit: int):
    """صف طبقه‌بندی: P0..P4، سپس نامشخص؛ در هر سطح retrieved تازه‌تر اول."""
    rank = case(
        *[(func.upper(Document.ingestion_priority) == lvl, i)
          for lvl, i in PRIORITY_RANK.items()],
        else_=UNKNOWN_RANK,
    )
    return (
        select(Article)
        .outerjoin(Document, Article.document_id == Document.id)
        .where(
            Article.classification_status == "pending",
            Article.classification_attempts < MAX_ATTEMPTS,
        )
        .order_by(rank, Article.retrieved_at.desc().nullslast(), Article.id)
        .limit(limit)
    )


def low_priority_level(article) -> str | None:
    """سطح قطعی P3/P4 از فیلد معتبر داکیومنت؛ نامشخص/نامعتبر -> None.

    مقدار گمشده هرگز کم‌اهمیت فرض نمی‌شود (گیت فقط روی P3/P4 صریح).
    """
    level, _ = _doc_priority(article)
    norm = str(level or "").strip().upper()
    return norm if norm in LOW_PRIORITY_SKIP else None


def apply_low_priority_skip(article, level: str) -> None:
    """تکمیل قطعی بدون AI برای P3/P4: لبه‌ی کم‌خطر باند، بدون ادعای AI.

    attempts مصرف نمی‌شود، شکست ثبت نمی‌شود، وضعیت done می‌شود تا چرخه
    تکراری رخ ندهد. منشأ از همان نگاشت decided (rules/ai) وگرنه None.
    """
    _, psrc = _doc_priority(article)
    decided = DECIDED_SOURCES.get(str(psrc or "").strip().lower())
    article.topics = "[]"
    article.entities = "[]"
    article.sentiment = None
    article.importance = PRIORITY_BANDS[level][0]
    article.decided_by = decided
    article.confidence = None
    article.classification_status = "done"
    article.classification_error = None
    article.classification_meta = json.dumps({
        "skipped_ai": "low_priority_gate",
        "level": level,
        "decided_by": decided,
        # گیت P3/P4 هیچ امتیاز تحلیلی محاسبه نمی‌کند؛ پس مقدار اولیه «نامعلوم» است
        # (نه صفر/عدد ساختگی) و محدودسازی باند قابل بازسازی نیست.
        "analytic_importance": None,
        "band_clamped": None,
        "classified_at": datetime.now(UTC).isoformat(),
    }, ensure_ascii=False)


def compute_novelty(db: Session, article: Article) -> float:
    """Novelty deterministic: چه مقدار از این خبر تازه/غیرتکراری است.

    بر پایه‌ی اندازه‌ی خوشه‌ی تکراری در ۷ روز گذشته. خوشه‌ی بزرگ → novelty کم.
    """
    since = datetime.now(UTC) - timedelta(days=7)
    cluster = article.duplicate_cluster
    if not cluster:
        return 1.0
    count = db.execute(
        select(func.count(Article.id)).where(
            Article.duplicate_cluster == cluster, Article.retrieved_at >= since
        )
    ).scalar_one()
    if count <= 1:
        return 1.0
    return max(0.0, 1.0 - (count - 1) * 0.2)


def compute_historical_significance(topic_count: int, entity_count: int) -> float:
    """تخمین ساده‌ی اهمیت تاریخی از غنای موضوع/موجودیت."""
    score = min(1.0, (topic_count * 0.15) + (entity_count * 0.1))
    return round(score, 3)


def compute_importance(inputs: ImportanceInputs) -> int:
    """محاسبه‌ی deterministic اهمیت از ۱ (بسیار مهم) تا ۱۰ (عادی)."""
    weights = {
        "impact": 0.18,
        "scope": 0.11,
        "probability": 0.07,
        "novelty": 0.11,
        "market_relevance": 0.13,
        "geopolitical_relevance": 0.09,
        "economic_relevance": 0.11,
        "time_sensitivity": 0.06,
        "strategic_relevance": 0.06,
        "historical_significance": 0.08,
    }
    values = inputs.as_dict()
    score = sum(values[k] * w for k, w in weights.items())
    score = max(0.0, min(1.0, score))
    importance = round(1 + (1 - score) * 9)
    return int(max(1, min(10, importance)))


# نگاشت مرکزی سطح اولویت بات (P0..P4) به باند Article.importance.
# عدد کمتر = مهم‌تر؛ تنها نقطه‌ی تبدیل در کل پروژه (تبدیل پراکنده ممنوع).
PRIORITY_BANDS: dict[str, tuple[int, int]] = {
    "P0": (1, 2),
    "P1": (3, 4),
    "P2": (5, 6),
    "P3": (7, 8),
    "P4": (9, 10),
}
# منشأهای معتبر تصمیم؛ بقیه (از جمله ناشناخته) -> None، هرگز جعل نمی‌شود.
DECIDED_SOURCES: dict[str, str] = {"rules": "rules", "ai": "ai"}


def align_importance_to_level(level: str | None, analytic: int, *,
                              priority_source: str | None = None,
                              ) -> tuple[int, str | None]:
    """هم‌راستاسازی قطعی مقدار تحلیلی با باند سطح اولویت.

    - مقدار درون باند حفظ می‌شود و decided آن NULL می‌ماند (منشأ عدد،
      فرمول تحلیلی است نه تصمیم جدید)؛ بیرون باند به نزدیک‌ترین لبه clamp
      می‌شود و فقط در این صورت decided از منشأ priority ثبت می‌شود.
    - سطح نامعتبر یا منشأ ناشناخته -> decided=None؛ هرگز جعل نمی‌شود.
    - امتیاز خام و confidence لمس نمی‌شوند؛ اجرای مجدد idempotent است.
    """
    band = PRIORITY_BANDS.get(str(level or "").strip().upper())
    if band is None:
        return analytic, None
    lo, hi = band
    if lo <= analytic <= hi:
        return analytic, None
    decided = DECIDED_SOURCES.get(str(priority_source or "").strip().lower())
    return (lo if analytic < lo else hi), decided


def _doc_priority(article) -> tuple[str | None, str | None]:
    """سطح و منشأ اولویت بات از Document همان مقاله (یا None برای قدیمی/API)."""
    doc = getattr(article, "document", None)
    if doc is None:
        return None, None
    return (getattr(doc, "ingestion_priority", None),
            getattr(doc, "priority_source", None))


@dataclass
class ClassifyOutcome:
    classified: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _article_text(article: Article) -> str:
    # AUDIT-REPAIR: متن کامل سند هم لحاظ می‌شود (قبلاً فقط title+summary که
    # summary در ingest تهی بود). ترتیب اهمیت: عنوان، خلاصه، بدنه.
    parts = [article.title or ""]
    document = article.document
    body = (document.raw_text if document is not None else None) or ""
    summary = (article.summary or "").strip()
    # خلاصهٔ قطعی محلی پیشوندِ همان بدنه است؛ دوباره‌افزودنش prompt را بی‌دلیل
    # بلند می‌کند و بدنه را از پنجرهٔ ۴۰۰۰ حرفی بیرون می‌اندازد. خلاصهٔ AI
    # (که پیشوند بدنه نیست) مثل قبل افزوده می‌شود.
    if summary and not body.startswith(summary):
        parts.append(summary)
    if body:
        parts.append(body)
    return "\n".join(p for p in parts if p).strip()


class ArticleClassifier:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    async def classify_article(self, article: Article) -> ClassificationResult:
        text = _article_text(article)
        if not text:
            raise ValueError("empty article text")

        prompt = CLASSIFY_ARTICLE.render(
            topics=", ".join(sorted(ALLOWED_TOPICS)),
            entity_types=", ".join(sorted(ALLOWED_ENTITY_TYPES)),
            text=text[:4000],
        )
        request = AIRequest(
            messages=[
                Message.system("You output strict JSON compatible with the schema."),
                Message.user(prompt),
            ],
            role="fast_extraction",
            task="classify_article",
            temperature=0.1,
            json_schema=CLASSIFY_SCHEMA,
            metadata={"prompt_version": CLASSIFY_ARTICLE.version},
        )
        response = await self.gateway.structured_generate(request, CLASSIFY_SCHEMA)
        data = response.structured or _safe_json(response.text)
        repair_attempted = False
        if not isinstance(data, dict):
            # FALLBACK مستند: مدل responseMimeType را رعایت نکرد؛ یک retry با
            # دستور صریح «فقط JSON» (parse + validate + یک retry).
            repair_attempted = True
            logger.warning("classify non-JSON output; one repair retry | article=%s", article.id)
            repair_request = AIRequest(
                messages=[
                    Message.system(
                        "You output ONLY a JSON object compatible with the schema. "
                        "No prose, no markdown fences, no explanations."
                    ),
                    Message.user(prompt),
                ],
                role="fast_extraction",
                task="classify_article",
                temperature=0.0,
                json_schema=CLASSIFY_SCHEMA,
                metadata={"prompt_version": f"{CLASSIFY_ARTICLE.version}+repair1"},
            )
            response = await self.gateway.structured_generate(repair_request, CLASSIFY_SCHEMA)
            data = response.structured or _safe_json(response.text)
        if not isinstance(data, dict):
            raise ValueError("provider did not return a JSON object (after 1 repair retry)")

        # اعتبارسنجی با jsonschema
        try:
            _validate(data, CLASSIFY_SCHEMA)
        except ValueError as exc:
            if repair_attempted:
                raise
            # FALLBACK مستند: اعتبارسنجی ناموفق؛ یک retry با دستور صریح.
            logger.warning("classify schema-invalid; one repair retry | article=%s", article.id)
            repair_request = AIRequest(
                messages=[
                    Message.system(
                        "You output ONLY a JSON object compatible with the schema. "
                        "No prose, no markdown fences, no explanations."
                    ),
                    Message.user(prompt),
                ],
                role="fast_extraction",
                task="classify_article",
                temperature=0.0,
                json_schema=CLASSIFY_SCHEMA,
                metadata={"prompt_version": f"{CLASSIFY_ARTICLE.version}+repair1"},
            )
            response = await self.gateway.structured_generate(repair_request, CLASSIFY_SCHEMA)
            data = response.structured or _safe_json(response.text)
            if not isinstance(data, dict):
                raise ValueError(
                    "provider did not return a JSON object (after 1 repair retry)"
                ) from exc
            _validate(data, CLASSIFY_SCHEMA)
            repair_attempted = True

        result = ClassificationResult.from_dict(data)
        result.repair_retry = repair_attempted
        result.prompt_version = response.prompt_version or CLASSIFY_ARTICLE.version
        result.provider = response.provider
        result.model = response.model
        result.is_mock = response.is_mock
        return result

    async def classify_pending(self, *, limit: int = 20) -> ClassifyOutcome:
        """مقالات pending با تلاش کمتر از حد مجاز را پردازش می‌کند.

        Stage89: screening decides **dispatch**, not classification. Every
        pending article is classified as before, so existing classifier
        contracts and decisions are preserved; the screening decision is stored
        as provenance and only gates downstream analysis:
        - True  -> event/claim/evidence dispatch rows are enqueued once.
        - False -> article retained; no ordinary analysis job is created.
        - None  -> a durable `screening` retry row is enqueued (never treated
          as irrelevant).
        """
        articles = list(self.db.execute(_pending_stmt(limit)).scalars().all())
        outcome = ClassifyOutcome()
        # Historical mock rows must not enter new classification in production.
        # Dev/test (mock_mode) keeps existing behavior: everything is processed.
        mock_ids: set = set()
        if not effective_mock_mode() and articles:
            from backend.database.models.document import mock_document_ids

            mock_ids = mock_document_ids(
                self.db, [a.document_id for a in articles]
            )
        for article in articles:
            if article.document_id in mock_ids:
                outcome.skipped += 1
                continue
            skipped_level = low_priority_level(article)
            if skipped_level is not None:
                apply_low_priority_skip(article, skipped_level)
                outcome.skipped += 1
                logger.info("classify skipped low priority | article=%s level=%s",
                            article.id, skipped_level)
                self.db.commit()
                continue

            # Screening is advisory for dispatch only; it never blocks or
            # rewrites the classification decision.
            screening = await self._screen(article)

            try:
                result = await self.classify_article(article)
            except AIError as exc:
                if exc.kind in (AIErrorKind.budget, AIErrorKind.quota_exhausted,
                                AIErrorKind.free_unavailable):
                    logger.warning("classify quota exhausted, kept pending | article=%s",
                                   article.id)
                    outcome.skipped += 1
                    continue
                self._record_failure(article, outcome, exc)
                self.db.commit()
                continue
            except Exception as exc:  # noqa: BLE001
                self._record_failure(article, outcome, exc)
                self.db.commit()
                continue
            article.classification_attempts = (article.classification_attempts or 0) + 1
            try:
                if result.is_mock and not effective_mock_mode():
                    raise ValueError("mock result rejected in production mode")

                self._apply(article, result, screening)
                article.classification_status = "done"
                article.classification_error = None
                outcome.classified += 1

                # Same transaction as the classification commit: a crash can
                # never persist a screening decision without its dispatch rows.
                dispatch_svc = DispatchService(self.db)
                dispatch_svc.enqueue_after_screening(article.id, screening)
            except Exception as exc:  # noqa: BLE001
                self._record_failure(article, outcome, exc)
            self.db.commit()

        logger.info(
            "classify done | classified=%d failed=%d skipped=%d",
            outcome.classified, outcome.failed, outcome.skipped,
        )
        return outcome

    def _record_failure(self, article: Article, outcome: ClassifyOutcome,
                          exc: Exception) -> None:
        """ثبت یکسان شکست (attempts، وضعیت، خطا) برای همه‌ی مسیرهای خطا."""
        article.classification_attempts = (article.classification_attempts or 0) + 1
        article.classification_error = f"{type(exc).__name__}: {exc}"[:2000]
        article.classification_status = (
            "failed" if article.classification_attempts >= MAX_ATTEMPTS else "pending"
        )
        outcome.failed += 1
        outcome.errors.append(f"article={article.id}: {exc}")
        logger.warning("classify failed | article=%s err=%s", article.id, exc)

    async def _screen(self, article: Article):
        """One screening entry point: orchestrator + supervisor + AI fallback.

        The legacy ``LocalScreener`` (ports 8009/8011) is not reachable from
        this path. ``local_screening_enabled`` is deprecated and intentionally
        not read; only the per-model panel flags decide local execution.
        """
        from backend.ai.local_screening import orchestrator as orch

        level, _ = _doc_priority(article)
        text = _article_text(article)
        try:
            return await orch.screen_with_db(self.db, text, level)
        except Exception as exc:  # noqa: BLE001
            logger.warning("screening error | article=%s err=%s",
                           article.id, type(exc).__name__)
            return orch.ScreeningDecision(
                route="ERROR",
                relevant=None,
                reason_codes=[f"SCREENING_EXCEPTION:{type(exc).__name__}"],
                fallback_used=False,
                p0_p1_safeguard=False,
                downstream_dispatch=False,
                provenance={"error": type(exc).__name__},
            )

    def _apply(self, article: Article, result: ClassificationResult,
               screening=None) -> None:
        # novelty و historical significance از سیستم
        result.importance_inputs.novelty = compute_novelty(self.db, article)
        result.importance_inputs.historical_significance = compute_historical_significance(
            len(result.topics), len(result.entities)
        )

        article.topics = json.dumps(result.topics, ensure_ascii=False)
        article.entities = json.dumps(
            [e.as_dict() for e in result.entities], ensure_ascii=False
        )
        article.sentiment = result.sentiment
        article.stance = result.stance
        article.country = result.country
        if result.summary:
            article.summary = result.summary[:2000]
        analytic = compute_importance(result.importance_inputs)
        level, psrc = _doc_priority(article)
        article.importance, article.decided_by = align_importance_to_level(
            level, analytic, priority_source=psrc)
        article.confidence = result.confidence
        # شفاف‌سازی محدودسازی: مقدار تحلیلی واقعی پیش از باند و اینکه باند آن را
        # تغییر داده یا نه. `null` یعنی باند معتبری نبود (تصمیم بازسازی‌ناپذیر)،
        # نه اینکه «تغییر نکرده»؛ مقدار جایگزین نمی‌سازیم.
        band = PRIORITY_BANDS.get(str(level or "").strip().upper())
        band_clamped = None if band is None else article.importance != analytic

        # متادیتای اجرا برای Reproducibility
        meta = {
            "provider": result.provider,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "is_mock": result.is_mock,
            "repair_retry": result.repair_retry,
            "classified_at": datetime.now(UTC).isoformat(),
            "importance_inputs": result.importance_inputs.as_dict(),
            "analytic_importance": analytic,
            "band_clamped": band_clamped,
            "response_hash": hashlib.sha256(
                json.dumps(result.topics, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16],
        }
        if screening is not None:
            # Advisory only: never written as a classification decision.
            meta["local_screening"] = screening.as_dict()
        article.classification_meta = json.dumps(meta, ensure_ascii=False)

        # Create/update classification dispatch record (idempotent)
        dispatch_svc = DispatchService(self.db)
        dispatch = dispatch_svc.ensure_dispatch(
            article.id,
            "classification",
            meta={
                "screening_route": screening.route if hasattr(screening, 'route') else None,
                "screening_decision": screening.relevant if hasattr(screening, 'relevant') else None,
            },
        )
        dispatch_svc.mark_completed(dispatch, meta={"provider": result.provider, "model": result.model})


def _validate(data: dict, schema: dict) -> None:
    try:
        import jsonschema

        jsonschema.validate(instance=data, schema=schema)
    except ImportError:  # pragma: no cover - اگر jsonschema نصب نبود
        # AUDIT-REPAIR: سکوت ممنوع؛ نبود اعتبارسنج باید دیده شود
        logger.warning("jsonschema not installed; skipping validation")
        return
    except Exception as exc:
        raise ValueError(f"schema validation failed: {exc}") from exc


def _safe_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None
