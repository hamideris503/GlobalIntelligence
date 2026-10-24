"""Deterministic domain routing for screened articles (Stage92).

The binary screening decision says the article is inside
``relevance_scope_v2``; it does not say which domain-analysis area applies.
This module derives domains **only** from signals the classification stage
already persists — never from a new classifier:

* ``Article.topics``      (JSON list, restricted to ``ALLOWED_TOPICS``)
* ``Article.country``     (ISO alpha-2; only ``IR`` maps to ``iran`` today)
* ``Event.event_type``    (reuses ``domains.worldstate.signals`` constants)

The result is persisted in ``classification_meta["domain_routing"]`` — the
same no-migration pattern as ``local_screening`` — with an explicit state and
reason codes. Relevance, domain assignment and P0-P4 priority stay separate
concepts; priority is never read here.

``DOMAINS`` is the audited routing matrix: an engine is listed as
``per_article=True`` only when a real, callable per-article entry point exists
in this repo (verified in the Stage92 audit) AND it is dispatched. Stage93
connected the first two domains via additive bounded-filter adapters
(geopolitics: per-actor filter; society: per-scope filter) — each still
computes over the engine's full bucket, so the analysis semantics are
unchanged. Aggregate/period engines without such an adapter are listed with
their exact integration gap and are **not** dispatched per article.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from domains.news.classifier_schema import ALLOWED_TOPICS
from domains.worldstate.signals import (
    CONFLICT_TYPES,
    POLITICAL_TYPES,
    SOCIAL_TYPES,
)
from sqlalchemy.orm import Session

ROUTING_VERSION = "domain_routing_v1"

# Every persisted classification topic -> its domain area. The keys are
# exactly ALLOWED_TOPICS; any unknown topic is ignored (never invented).
TOPIC_DOMAINS: dict[str, str] = {
    "macroeconomics": "macro",
    "monetary_policy": "macro",
    "fiscal_policy": "macro",
    "inflation": "macro",
    "employment": "macro",
    "trade": "macro",
    "commodities": "markets",
    "markets": "markets",
    "equities": "markets",
    "fixed_income": "markets",
    "fx": "markets",
    "crypto": "markets",
    "energy": "energy",
    "geopolitics": "geopolitics",
    "conflict": "geopolitics",
    "sanctions": "geopolitics",
    "politics": "politics",
    "society": "society",
    "technology": "technology",
    "health": "health",
    "climate": "climate",
}

COUNTRY_DOMAINS: dict[str, str] = {"IR": "iran"}

_EVENT_TYPE_DOMAINS: dict[str, str] = {
    **{t: "society" for t in SOCIAL_TYPES},
    **{t: "geopolitics" for t in CONFLICT_TYPES},
    **{t: "politics" for t in POLITICAL_TYPES},
}

# Reason codes.
DOMAIN_NO_SIGNAL = "DOMAIN_NO_SIGNAL"          # no topic / country / event input
DOMAIN_NO_ENGINE = "DOMAIN_NO_ENGINE"          # no per-article engine for a domain
DOMAIN_NO_DISPATCH = "DOMAIN_NO_DISPATCH"      # documented gap: aggregate engine


_MATRIX: dict[str, dict[str, Any]] = {
    "iran": {
        "engine": "domains.iran.brief.IranModeService.brief",
        "per_article": False,
        "gap": "brief() is a read model over ALL IR events for one call; refreshing "
               "it per article would be a recompute fan-out. Needs an aggregate "
               "refresh task, not per-article dispatch.",
    },
    "macro": {
        "engine": "domains.macro.analysis.MacroEngine.analyze_all(indicator, country)",
        "per_article": False,
        "gap": "consumes MacroObservation series per indicator+country; an article "
               "carries neither. Needs MacroObservation ingestion (markets data) "
               "and an indicator mapping from persisted signals.",
    },
    "markets": {
        "engine": "domains.markets.engine.MarketDataService",
        "per_article": False,
        "gap": "pure data ingestion (quote fetchers); no article input contract.",
    },
    "energy": {
        "engine": None,
        "per_article": False,
        "gap": "no energy engine exists in this repo.",
    },
    "geopolitics": {
        "engine": "domains.geopolitics.analysis.GeopoliticalEngine.analyze_all",
        "per_article": True,
        "task": "domain_geopolitics",
        "gap": "connected in Stage93 via the additive per-call `actors` filter: "
               "only the article event's actors are recomputed, each over its "
               "FULL per-period bucket (analysis semantics unchanged). Without "
               "the filter the call recomputes every actor.",
    },
    "society": {
        "engine": "domains.society.analysis.SocialEngine.analyze_all",
        "per_article": True,
        "task": "domain_society",
        "gap": "connected in Stage93 via the additive per-call `scopes` filter: "
               "only the article's (topic, country) scopes are recomputed, "
               "each from ALL of that scope's done articles (mood semantics "
               "unchanged). Without the filter the call recomputes every scope.",
    },
    "politics": {
        "engine": None,
        "per_article": False,
        "gap": "no dedicated politics engine; POLITICAL_TYPES events belong to "
               "geopolitics aggregates today.",
    },
    "technology": {
        "engine": None,
        "per_article": False,
        "gap": "no technology engine exists in this repo.",
    },
    "health": {
        "engine": None,
        "per_article": False,
        "gap": "no health engine exists in this repo.",
    },
    "climate": {
        "engine": None,
        "per_article": False,
        "gap": "no climate engine exists in this repo.",
    },
}

# Domains with a real per-article dispatch entry point. The task is created by
# the `domain_routing` handler ONLY when the article's routing includes the
# domain — never for every relevant article.
DOMAIN_TASKS: dict[str, str] = {
    "geopolitics": "domain_geopolitics",
    "society": "domain_society",
}


def _parse_topics(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, str) and t in ALLOWED_TOPICS]


def route_article(article) -> dict[str, Any]:
    """Derive domain routing purely from persisted classification signals.

    Reads (not writes): ``Article.topics``, ``Article.country`` and the linked
    event's ``event_type``. Returns the ``domain_routing`` payload.
    """
    topics = _parse_topics(article.topics)
    country = (article.country or "").upper() or None
    event_type = None
    event = getattr(article, "event", None)
    if event is not None:
        event_type = event.event_type or None

    domains: list[str] = []
    signals: dict[str, Any] = {"topics": topics, "country": country, "event_type": event_type}

    for topic in topics:
        d = TOPIC_DOMAINS.get(topic)
        if d and d not in domains:
            domains.append(d)
    if country and country in COUNTRY_DOMAINS:
        d = COUNTRY_DOMAINS[country]
        if d not in domains:
            domains.append(d)
    if event_type and event_type in _EVENT_TYPE_DOMAINS:
        d = _EVENT_TYPE_DOMAINS[event_type]
        if d not in domains:
            domains.append(d)

    reason_codes: list[str] = []
    if not domains:
        state = "unassigned"
        reason_codes.append(DOMAIN_NO_SIGNAL)
    else:
        ready = [d for d in domains if _matrix_entry(d)["per_article"]]
        missing = [d for d in domains if d not in ready]
        if ready:
            state = "assigned"
        elif missing:
            state = "pending"
        for d in missing:
            code = f"{DOMAIN_NO_ENGINE}:{d}" if _matrix_entry(d)["engine"] is None \
                else f"{DOMAIN_NO_DISPATCH}:{d}"
            if code not in reason_codes:
                reason_codes.append(code)
        signals["unconnected_domains"] = missing
        signals["per_article_ready"] = ready

    return {
        "version": ROUTING_VERSION,
        "domains": domains,
        "state": state,
        "reason_codes": reason_codes,
        "signals": signals,
    }


def _matrix_entry(domain: str) -> dict[str, Any]:
    return _MATRIX.get(domain, {"engine": None, "per_article": False, "gap": "unknown domain"})


def domain_matrix() -> dict[str, Any]:
    """The routing matrix, for the report and operational visibility."""
    return {d: dict(v) for d, v in _MATRIX.items()}


def persist_domain_routing(db: Session, article) -> dict[str, Any]:
    """Write ``classification_meta["domain_routing"]`` beside the screening meta.

    No migration: ``classification_meta`` is the existing JSON metadata column.
    The article is never modified beyond this metadata; a missing classification
    leaves explicit pending state untouched.
    """
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    routing = route_article(article)
    meta["domain_routing"] = routing
    article.classification_meta = json.dumps(meta, ensure_ascii=False)
    db.flush()
    return routing


def refresh_domain_routing(
    db: Session, article, *, triggered_by_event: uuid.UUID | None = None
) -> dict[str, Any]:
    """Recompute domain routing from now-persisted state and create missing work.

    Called only after event extraction has committed (the event's actors and
    ``event_type`` are real persisted signals). Never infers actors or domains:
    it reuses ``route_article`` over the article's current persisted fields and
    dispatches only domains that are newly eligible and not already tracked.

    Returns ``{"changed": bool, "domains": [...], "state": ..., "created_tasks": [...]}``.
    """
    try:
        meta = json.loads(article.classification_meta or "{}")
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    previous = meta.get("domain_routing")
    previous = previous if isinstance(previous, dict) else {}

    # Refresh from DB so a stale cached relationship (e.g. article.event
    # cached as None before the event was linked) cannot mask newly persisted
    # signals. expire_on_commit=False (conftest/production) keeps expired
    # objects in the identity map, which is why this explicit refresh is
    # required.
    db.refresh(article)

    routing = route_article(article)
    previous_domains = list(previous.get("domains") or [])
    new_domains = list(routing.get("domains") or [])

    from backend.ai.dispatch.service import DispatchService

    service = DispatchService(db)
    created_tasks: list[str] = []
    for domain in new_domains:
        if domain in previous_domains:
            continue  # already tracked; never repeat completed domain work
        task = DOMAIN_TASKS.get(domain)
        if task is None:
            continue  # routed but no real per-article engine: reason code stands
        service.ensure_dispatch(article.id, task, meta={"domain": domain})
        created_tasks.append(task)

    # Preserve history without erasing the original screening provenance or any
    # other classification_meta keys.
    refresh = {
        "method": "event_driven_refresh",
        "triggered_by_event": str(triggered_by_event) if triggered_by_event else None,
        "triggered_at": datetime.now(UTC).isoformat(),
        "previous_domains": previous_domains,
        "domains": new_domains,
    }
    history = list(previous.get("refresh_history") or [])
    history.append(refresh)
    routing["refresh_history"] = history
    routing["previous_domains"] = previous_domains
    meta["domain_routing"] = routing
    article.classification_meta = json.dumps(meta, ensure_ascii=False)
    db.flush()
    return {
        "changed": created_tasks != [] or previous_domains != new_domains,
        "domains": new_domains,
        "state": routing["state"],
        "created_tasks": created_tasks,
    }


__all__ = [
    "DOMAIN_NO_DISPATCH",
    "DOMAIN_NO_ENGINE",
    "DOMAIN_NO_SIGNAL",
    "DOMAIN_TASKS",
    "COUNTRY_DOMAINS",
    "ROUTING_VERSION",
    "TOPIC_DOMAINS",
    "domain_matrix",
    "persist_domain_routing",
    "refresh_domain_routing",
    "route_article",
]
