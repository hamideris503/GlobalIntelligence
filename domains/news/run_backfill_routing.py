"""Run historical domain-routing backfill planner (Stage97).

Default mode is dry-run (read-only). Use ``--apply`` to create missing
dispatch rows via the existing idempotent services.

Usage:
    python -m domains.news.run_backfill_routing --limit 500
    python -m domains.news.run_backfill_routing --limit 500 --apply
    python -m domains.news.run_backfill_routing --limit 500 --apply --batch-size 50
"""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from backend.ai.dispatch.routing import (
    DOMAIN_TASKS,
    refresh_domain_routing,
)
from backend.ai.dispatch.service import task_key
from backend.database.base import Base
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.session import get_session_factory


def _classify(article: Article) -> dict:
    """Classify an article into a pre-Stage94 routing category (read-only)."""
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}

    screening = meta.get("local_screening")
    screening = screening if isinstance(screening, dict) else {}
    decision = screening.get("decision")

    dr = meta.get("domain_routing")
    dr = dr if isinstance(dr, dict) else None

    if dr is None:
        category = "no_routing"
    elif not dr.get("refresh_history"):
        if dr.get("state") == "unassigned":
            category = "unassigned"
        else:
            category = "pre_stage94"
    else:
        category = "stage94_plus"

    # Check if event is linked
    has_event = article.event_id is not None

    # Check missing dispatches
    missing_tasks = []
    if dr is not None and decision is True:
        for domain in dr.get("domains", []):
            task = DOMAIN_TASKS.get(domain)
            if task:
                missing_tasks.append(task)

    return {
        "article_id": str(article.id),
        "category": category,
        "decision": decision,
        "has_event": has_event,
        "domains": dr.get("domains", []) if dr else [],
        "state": dr.get("state") if dr else None,
        "reason_codes": dr.get("reason_codes", []) if dr else [],
        "missing_tasks": missing_tasks,
    }


def _scan(session, limit: int, batch_size: int) -> dict:
    """Scan articles and produce inventory. Read-only in dry-run."""
    articles = list(session.execute(
        select(Article)
        .where(Article.classification_status == "done")
        .order_by(Article.retrieved_at.desc().nullslast())
        .limit(limit)
    ).scalars().all())

    categories = {"no_routing": 0, "pre_stage94": 0, "stage94_plus": 0, "unassigned": 0}
    eligible_refresh = 0
    missing_dispatch = 0
    skip = 0
    ambiguous = 0
    affected_ids = []

    for art in articles:
        info = _classify(art)
        categories[info["category"]] += 1

        # Determine if eligible for routing refresh
        if info["decision"] is True:
            if info["category"] in ("no_routing", "pre_stage94", "unassigned"):
                if info["has_event"] or info["category"] == "no_routing":
                    eligible_refresh += 1
                    affected_ids.append(info["article_id"])
            # Check missing dispatches
            if info["missing_tasks"]:
                # Verify they don't already exist
                for task in info["missing_tasks"]:
                    exists = session.execute(
                        select(ArticleDispatch.id).where(
                            ArticleDispatch.article_id == art.id,
                            ArticleDispatch.task_name == task_key(task),
                        )
                    ).first()
                    if exists is None:
                        missing_dispatch += 1
                        if info["article_id"] not in affected_ids:
                            affected_ids.append(info["article_id"])
        else:
            skip += 1

        # Ambiguous: has routing but no screening decision
        if info["decision"] is None and info["category"] != "no_routing":
            ambiguous += 1

    # Deterministic sample (first 20 sorted IDs)
    sample_ids = sorted(affected_ids)[:20]

    return {
        "total_scanned": len(articles),
        "categories": categories,
        "eligible_refresh": eligible_refresh,
        "missing_dispatch": missing_dispatch,
        "skip": skip,
        "ambiguous": ambiguous,
        "affected_ids": affected_ids,
        "sample_ids": sample_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Historical domain-routing backfill planner (dry-run by default)"
    )
    parser.add_argument("--limit", type=int, default=500,
                        help="Max articles to scan")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Batch size for apply mode")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes (default: dry-run)")
    parser.add_argument("--manifest", type=str, default=None,
                        help="Path to write run manifest JSON")
    args = parser.parse_args()

    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()
    mode = "apply" if args.apply else "dry-run"

    session = get_session_factory()()
    # Ensure tables exist (for fresh databases)
    Base.metadata.create_all(bind=session.bind)
    try:
        # Dry-run scan
        inventory = _scan(session, args.limit, args.batch_size)

        print(json.dumps({
            "run_id": run_id,
            "mode": mode,
            "started_at": started_at,
            "database_dialect": session.bind.dialect.name,
            "total_scanned": inventory["total_scanned"],
            "categories": inventory["categories"],
            "eligible_refresh": inventory["eligible_refresh"],
            "missing_dispatch": inventory["missing_dispatch"],
            "skip": inventory["skip"],
            "ambiguous": inventory["ambiguous"],
            "sample_ids": inventory["sample_ids"],
        }, ensure_ascii=False, indent=2))

        if not args.apply:
            print("\nDry-run complete. No changes made.")
            print(f"Use --apply to create {inventory['missing_dispatch']} missing dispatch records.")
            # Write manifest
            manifest = {
                "run_id": run_id,
                "mode": mode,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "database_dialect": session.bind.dialect.name,
                "selection_criteria": "classification_status=done, screening decision=True",
                "records_scanned": inventory["total_scanned"],
                "records_selected": len(inventory["affected_ids"]),
                "records_updated": 0,
                "records_skipped": inventory["skip"],
                "records_failed": 0,
                "dispatches_created": 0,
                "dispatches_already_present": 0,
                "affected_ids_hash": hashlib.sha256(
                    json.dumps(sorted(inventory["affected_ids"])).encode()
                ).hexdigest(),
                "status": "dry-run complete",
            }
            if args.manifest:
                with open(args.manifest, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)
                print(f"Manifest written to {args.manifest}")
            return 0

        # Apply mode
        print(f"\nApply mode: processing {len(inventory['affected_ids'])} articles...")
        processed = 0
        updated = 0
        skipped = 0
        failed = 0
        created = 0
        already_present = 0
        errors = []

        # Process in batches
        affected = inventory["affected_ids"]
        for i in range(0, len(affected), args.batch_size):
            batch = affected[i:i + args.batch_size]
            for aid in batch:
                try:
                    art = session.get(Article, uuid.UUID(aid))
                    if art is None:
                        failed += 1
                        errors.append({"id": aid, "error": "article not found"})
                        continue

                    # Preserve screening provenance
                    try:
                        meta = json.loads(art.classification_meta or "{}")
                    except (TypeError, ValueError):
                        meta = {}
                    if not isinstance(meta, dict):
                        meta = {}

                    # Run refresh (uses existing service)
                    result = refresh_domain_routing(session, art, triggered_by_event=art.event_id)
                    created.extend(result.get("created_tasks", []))
                    created_count = len(result.get("created_tasks", []))

                    processed += 1
                    if created_count > 0:
                        updated += 1
                    else:
                        skipped += 1

                    session.commit()
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    failed += 1
                    errors.append({"id": aid, "error": f"{type(exc).__name__}: {exc}"})
                    print(f"  ERROR on {aid}: {exc}")

            print(f"  Batch {i // args.batch_size + 1}: processed {len(batch)} articles")

        # Count already-present dispatches
        for aid in affected:
            art = session.get(Article, uuid.UUID(aid))
            if art is not None:
                meta = json.loads(art.classification_meta or "{}") if art.classification_meta else {}
                dr = meta.get("domain_routing", {}) if isinstance(meta, dict) else {}
                for domain in dr.get("domains", []):
                    task = DOMAIN_TASKS.get(domain)
                    if task:
                        exists = session.execute(
                            select(ArticleDispatch.id).where(
                                ArticleDispatch.article_id == art.id,
                                ArticleDispatch.task_name == task_key(task),
                            )
                        ).first()
                        if exists is not None:
                            already_present += 1

        # Adjust: already_present counts dispatches that existed before this run
        # created counts new ones. Don't double-count.
        already_present = max(0, already_present - len(created))

        manifest = {
            "run_id": run_id,
            "mode": mode,
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "database_dialect": session.bind.dialect.name,
            "selection_criteria": "classification_status=done, screening decision=True",
            "records_scanned": inventory["total_scanned"],
            "records_selected": len(affected),
            "records_updated": updated,
            "records_skipped": skipped,
            "records_failed": failed,
            "dispatches_created": len(created),
            "dispatches_already_present": already_present,
            "affected_ids_hash": hashlib.sha256(
                json.dumps(sorted(affected)).encode()
            ).hexdigest(),
            "errors": errors[:50],  # cap error list
            "status": "completed" if failed == 0 else "completed with errors",
        }

        print(json.dumps(manifest, ensure_ascii=False, indent=2))

        if args.manifest:
            with open(args.manifest, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            print(f"Manifest written to {args.manifest}")

        return 0 if failed == 0 else 1

    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
