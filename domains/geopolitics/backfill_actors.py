"""Backfill geopolitical actor arrays on existing events (Phase 22 supplement).

Existing events created in mock mode have empty ``actors`` arrays, so
``GeopoliticalEngine`` produces zero assessments. This module re-extracts
actors for those events using the AI path (real provider required) and
links them to canonical entities, then optionally runs geopolitics analysis.

Usage
-----
    # Read-only validation + dry-run preview (default, no writes, no AI):
    python -m domains.geopolitics.backfill_actors

    # Apply with a real provider (refuses to run in mock mode):
    python -m domains.geopolitics.backfill_actors --apply

    # Apply then run geopolitics tension analysis:
    python -m domains.geopolitics.backfill_actors --apply --analyze

    # Limit / force reprocessing:
    python -m domains.geopolitics.backfill_actors --apply --limit 50 --force

    # Machine-readable summary:
    python -m domains.geopolitics.backfill_actors --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.mock_mode import effective_mock_mode
from backend.database.models.article import Article
from backend.database.models.event import Event
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.session import get_session_factory
from domains.events.extractor import EVENT_SCHEMA, EXTRACT_EVENT, _resolve_actors, _safe_json
from domains.events.prompts import EXTRACT_EVENT as _P  # noqa: F401
from domains.geopolitics.analysis import GeopoliticalEngine


def _is_empty_actors(raw: str | None) -> bool:
    if raw is None:
        return True
    try:
        val = json.loads(raw)
    except Exception:  # noqa: BLE001
        return True
    if not isinstance(val, list):
        return True
    return not any(isinstance(x, str) and x.strip() for x in val)


def _event_text(articles: list[Article]) -> str:
    return "\n\n---\n\n".join(
        f"[{i + 1}] {(a.title or '')}\n{a.summary or ''}"
        for i, a in enumerate(articles[:8])
    )


def _schema_ok(db) -> tuple[bool, list[str]]:
    problems: list[str] = []
    try:
        db.execute(select(Event).limit(1))
    except Exception as exc:  # noqa: BLE001
        problems.append(f"events table unreadable: {type(exc).__name__}")
    try:
        db.execute(select(GeopoliticalAssessment).limit(1))
    except Exception as exc:  # noqa: BLE001
        problems.append(f"geopolitical_assessments table unreadable: {type(exc).__name__}")
    try:
        db.execute(select(Article).limit(1))
    except Exception as exc:  # noqa: BLE001
        problems.append(f"articles table unreadable: {type(exc).__name__}")
    return (not problems, problems)


def _provider_available() -> tuple[bool, str]:
    settings = get_settings()
    if effective_mock_mode():
        return False, "effective_mock_mode() is True (no real provider configured)"
    if (settings.ai_default_provider or "").strip().lower() == "mock":
        return False, "ai_default_provider is 'mock'"
    return True, f"ai_default_provider={settings.ai_default_provider}"


@dataclass
class BackfillOutcome:
    dry_run: bool
    provider_available: bool
    provider_detail: str
    schema_ok: bool
    schema_problems: list[str] = field(default_factory=list)
    events_total: int = 0
    events_empty_actors: int = 0
    events_with_actors: int = 0
    events_no_articles: int = 0
    limit: int = 0
    events_processed: int = 0
    events_updated: int = 0
    events_failed: int = 0
    events_skipped: int = 0
    actors_extracted: int = 0
    entities_before: int = 0
    entities_after: int = 0
    preview_candidates: int = 0
    preview_events: int = 0
    errors: list[str] = field(default_factory=list)
    analyze_outcome: dict | None = None

    def as_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "provider_available": self.provider_available,
            "provider_detail": self.provider_detail,
            "schema_ok": self.schema_ok,
            "schema_problems": self.schema_problems,
            "events_total": self.events_total,
            "events_empty_actors": self.events_empty_actors,
            "events_with_actors": self.events_with_actors,
            "events_no_articles": self.events_no_articles,
            "limit": self.limit,
            "events_processed": self.events_processed,
            "events_updated": self.events_updated,
            "events_failed": self.events_failed,
            "events_skipped": self.events_skipped,
            "actors_extracted": self.actors_extracted,
            "entities_before": self.entities_before,
            "entities_after": self.entities_after,
            "preview_candidates": self.preview_candidates,
            "preview_events": self.preview_events,
            "errors": self.errors,
            "analyze_outcome": self.analyze_outcome,
        }


def _count_entities(db) -> int:
    from sqlalchemy import func

    from backend.database.models.entity import Entity

    return int(db.execute(select(func.count()).select_from(Entity)).scalar() or 0)


async def _ai_actors_for_event(db, event: Event, articles: list[Article]) -> tuple[list[str], dict, str | None]:
    """Run the AI extraction path for one event's linked articles.

    Returns (resolved_actors, actor_resolution, error). On any failure returns
    ([], {...}, error_string) and performs no writes.
    """
    joined = _event_text(articles)
    metadata: dict[str, Any] = {}
    try:
        if effective_mock_mode():
            raise RuntimeError("mock_mode_active: no real provider configured")
        prompt = EXTRACT_EVENT.render(articles=joined[:8000])
        request = AIRequest(
            messages=[
                Message.system("You output strict JSON compatible with the schema."),
                Message.user(prompt),
            ],
            role="deep_analysis",
            task="extract_event",
            temperature=0.1,
            json_schema=EVENT_SCHEMA,
            metadata={"prompt_version": EXTRACT_EVENT.version},
        )
        response = await get_gateway().structured_generate(request, EVENT_SCHEMA)
        if getattr(response, "is_mock", False):
            raise RuntimeError("mock_provider_response: provider returned mock")
        data = response.structured or _safe_json(response.text) or {}
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:300]}"
        return [], {"source": "ai_failed", "error": err}, err

    resolved = _resolve_actors(db, data.get("actors"), joined, metadata)
    actor_resolution = metadata.get("actor_resolution", {})
    return resolved, actor_resolution, None


async def _run_backfill(
    db, *, apply: bool, limit: int, force: bool, outcome: BackfillOutcome
) -> None:
    from backend.database.models.entity import Entity  # noqa: F401

    events = list(db.execute(select(Event).order_by(Event.occurred_at.desc().nullslast())).scalars().all())
    outcome.events_total = len(events)
    empty_events = [e for e in events if _is_empty_actors(e.actors)]
    outcome.events_empty_actors = len(empty_events)
    outcome.events_with_actors = len(events) - len(empty_events)

    candidates = events if force else empty_events
    # events with no linked articles cannot be backfilled
    no_article_ids: list = []
    processable: list[Event] = []
    for e in candidates[: (limit if limit > 0 else None)]:
        articles = list(db.execute(select(Article).where(Article.event_id == e.id)).scalars().all())
        if not articles:
            no_article_ids.append(e.id)
            continue
        processable.append(e)
    outcome.events_no_articles = len(no_article_ids)

    if not apply:
        # Dry-run preview: deterministic extraction only, labelled as preview.
        preview_candidates = 0
        preview_events = 0
        for e in processable:
            articles = list(db.execute(select(Article).where(Article.event_id == e.id)).scalars().all())
            text = _event_text(articles)
            from domains.events.actor_extraction import extract_actors_deterministic

            cands = extract_actors_deterministic(text)
            if cands:
                preview_events += 1
                preview_candidates += len(cands)
        outcome.preview_candidates = preview_candidates
        outcome.preview_events = preview_events
        outcome.limit = limit
        return

    outcome.entities_before = _count_entities(db)
    outcome.limit = limit
    for e in processable:
        outcome.events_processed += 1
        articles = list(db.execute(select(Article).where(Article.event_id == e.id)).scalars().all())
        resolved, actor_resolution, err = await _ai_actors_for_event(db, e, articles)
        if err is not None:
            outcome.events_failed += 1
            outcome.errors.append(f"event {e.id}: {err}")
            continue
        try:
            e.actors = json.dumps(resolved, ensure_ascii=False)
            try:
                em = json.loads(e.event_metadata or "{}")
            except Exception:  # noqa: BLE001
                em = {}
            em["actor_resolution"] = actor_resolution
            em["actor_backfill"] = {
                "source": "ai",
                "at": datetime.now(UTC).isoformat(),
                "article_count": len(articles),
            }
            e.event_metadata = json.dumps(em, ensure_ascii=False)
            db.flush()
            outcome.events_updated += 1
            outcome.actors_extracted += len(resolved)
        except Exception as exc:  # noqa: BLE001
            outcome.events_failed += 1
            outcome.errors.append(f"event {e.id}: {type(exc).__name__}: {exc}")
    db.commit()
    outcome.entities_after = _count_entities(db)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill geopolitical actors on existing events")
    parser.add_argument("--apply", action="store_true", help="Apply changes (requires real AI provider)")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run (default)")
    parser.add_argument("--limit", type=int, default=0, help="Max events to process (0 = all empty-actor events)")
    parser.add_argument("--force", action="store_true", help="Reprocess events that already have actors")
    parser.add_argument("--analyze", action="store_true", help="Run GeopoliticalEngine.analyze_all() after apply")
    parser.add_argument("--period", type=str, default=None, help="Period for analysis (default: current month)")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    dry_run = not args.apply or args.dry_run

    db = get_session_factory()()
    try:
        outcome = BackfillOutcome(dry_run=dry_run, provider_available=False, provider_detail="", schema_ok=False, limit=args.limit)

        ok, problems = _schema_ok(db)
        outcome.schema_ok = ok
        outcome.schema_problems = problems

        prov_ok, prov_detail = _provider_available()
        outcome.provider_available = prov_ok
        outcome.provider_detail = prov_detail

        if not ok:
            if args.json:
                print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
            else:
                print("Schema problems:")
                for p in problems:
                    print(f"  - {p}")
            return 2

        if args.apply and not dry_run and not prov_ok:
            if args.json:
                print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(f"Refusing to apply: {prov_detail}")
                print("Set a real AI provider (MOCK_MODE=false, AI_DEFAULT_PROVIDER != mock) and retry.")
            return 2

        asyncio.run(_run_backfill(db, apply=(args.apply and not dry_run), limit=args.limit, force=args.force, outcome=outcome))

        if args.apply and not dry_run and args.analyze:
            geo = GeopoliticalEngine(db).analyze_all(period=args.period)
            outcome.analyze_outcome = geo.as_dict()

        if args.json:
            print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
        else:
            print("=== Geopolitics actor backfill ===")
            print(f"Mode: {'DRY-RUN (no writes)' if outcome.dry_run else 'APPLY'}")
            print(f"Schema: {'OK' if outcome.schema_ok else 'PROBLEMS'}")
            print(f"Provider: {'available' if outcome.provider_available else 'unavailable'} ({outcome.provider_detail})")
            print(f"Events total: {outcome.events_total}")
            print(f"Events with empty actors: {outcome.events_empty_actors}")
            print(f"Events with actors: {outcome.events_with_actors}")
            print(f"Events with no linked articles: {outcome.events_no_articles}")
            if outcome.dry_run:
                print(f"Preview (deterministic, not trusted): {outcome.preview_events} events / {outcome.preview_candidates} candidates")
            else:
                print(f"Processed: {outcome.events_processed}")
                print(f"Updated: {outcome.events_updated}")
                print(f"Actors extracted: {outcome.actors_extracted}")
                print(f"Failed: {outcome.events_failed}")
                print(f"Entities: {outcome.entities_before} -> {outcome.entities_after}")
            if outcome.analyze_outcome is not None:
                print(f"Geopolitics analyze: {outcome.analyze_outcome}")
            if outcome.errors:
                print("Errors:")
                for e in outcome.errors[:20]:
                    print(f"  - {e}")
        return 0 if (outcome.events_failed == 0) else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
