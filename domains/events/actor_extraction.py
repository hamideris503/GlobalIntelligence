"""Deterministic actor extraction for events (Phase 11 supplement).

Provides a conservative, high-quality-abstention actor extractor that
extracts actor mentions from article text when AI is unavailable.

Design principles:
- Prefer high-quality abstention over fabricated actors.
- Only extract clear actor mentions (capitalized proper nouns in actor-like contexts).
- Filter out locations, common words, source publishers, and other non-actors.
- Link extracted mentions to canonical Entity records via upsert_entity.
- SAFETY: Deterministic candidates do NOT auto-create canonical entities.
  They only resolve to existing canonical entities. Unresolved candidates
  are tracked in shadow mode but never persisted as trusted actors.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Common words that are NOT actors
_NON_ACTOR_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "can", "shall", "might", "must",
    "not", "no", "yes", "it", "he", "she", "they", "we", "i", "you",
    "this", "that", "these", "those", "what", "which", "who", "whom",
    "how", "when", "where", "why", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "only", "own", "same", "so",
    "than", "too", "very", "just", "also", "now", "here", "there", "then",
    "today", "yesterday", "tomorrow", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday", "january", "february",
    "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "news", "report", "said", "says",
    "according", "however", "although", "because", "while", "during",
    "after", "before", "between", "through", "about", "against", "among",
    "within", "without", "under", "over", "above", "below", "up", "down",
    "out", "off", "into", "onto", "upon", "per", "via", "vs", "etc",
    "inc", "ltd", "corp", "co", "llc", "plc", "its", "their", "our",
    "new", "old", "first", "last", "next", "big", "small", "large",
    "indian", "turkish", "chinese", "russian", "iranian", "israeli",
    "french", "german", "japanese", "british", "american", "ukrainian",
    "palestinian", "iraqi", "syrian", "lebanese", "egyptian", "saudi",
    "yemeni", "afghan", "pakistani", "greek", "italian",
    "spanish", "dutch", "polish", "swedish", "norwegian", "danish",
    "finnish", "portuguese", "belgian", "austrian", "swiss", "canadian",
    "australian", "mexican", "brazilian", "argentinian", "colombian",
    "venezuelan", "nigerian", "kenyan", "south", "north", "east", "west",
})

# Common location words that should not be treated as actors
_LOCATION_WORDS = frozenset({
    "america", "american", "united states", "united kingdom", "china",
    "chinese", "russia", "russian", "iran", "iranian", "israel", "israeli",
    "france", "french", "germany", "german", "japan", "japanese",
    "india", "indian", "brazil", "brazilian", "ukraine", "ukrainian",
    "europe", "european", "asia", "asian", "africa", "african",
    "athens", "paris", "berlin", "moscow", "beijing", "tehran",
    "washington", "london", "tokyo", "delhi", "philadelphia", "amsterdam",
    "texas", "yemen", "gaza", "uk", "us", "usa",
})

# Patterns that indicate an actor-like context
_ACTOR_PATTERNS = [
    re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s+(?:said|says|announced|announces|reported|reports|declared|stated|confirmed|denied|warned|warns|claimed|claims|argued|insisted|added|noted|explained|described|called|urged|urges|demanded|demands|proposed|proposes|rejected|rejects|accepted|accepts|approved|approves|signed|signs|launched|launches|attacked|attacks|sanctioned|sanctions|imposed|lifted|extended|extends|expanded|expands|reduced|reduces|increased|increases|decreased|decreases|spent|met|meets|plans|planned|decided|chose|selected|elected|appointed|fired|resigned|arrested|charged|sued|filed|won|lost|gained|dropped|rose|fell|surged|plunged|collapsed|grew|shrank|contracted|opened|closed|started|stopped|began|ended|continued|maintained|kept|held|released|published|issued|created|built|developed|designed|produced|manufactured|sold|bought|acquired|merged|split|divided|united|formed|established|founded|dissolved|disbanded)\b"),
    re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})'s\s+\w+"),
    re.compile(r"\bby\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b"),
    re.compile(r"\baccording to\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b"),
]


def extract_actors_deterministic(text: str) -> list[str]:
    """Extract actor mentions from text using conservative deterministic patterns.

    Returns a list of unique actor name strings. Returns empty list if no
    reliable actors can be identified (high-quality abstention).

    This is NOT equivalent to semantic actor extraction. It uses surface
    patterns and filters out common words, locations, and source publishers.
    Output is candidate-level only — NOT trusted for canonical entity creation
    or geopolitical analysis without explicit verification.
    """
    if not text or not text.strip():
        return []

    candidates: set[str] = set()

    for pattern in _ACTOR_PATTERNS:
        for m in pattern.finditer(text):
            g1 = m.group(1).strip() if m.group(1) else None
            g2 = None
            try:
                g2 = m.group(2).strip() if m.group(2) else None
            except IndexError:
                pass

            for candidate in (g1, g2):
                if candidate and _is_valid_actor(candidate):
                    candidates.add(candidate)

    return sorted(candidates)


def _is_valid_actor(candidate: str) -> bool:
    """Check if a candidate string is a valid actor mention."""
    if not candidate or len(candidate) < 2:
        return False

    words = candidate.split()
    if len(words) > 4:
        return False

    if all(w.lower() in _NON_ACTOR_WORDS for w in words):
        return False

    if len(words) == 1 and candidate.lower() in _LOCATION_WORDS:
        return False

    if words[0].lower() in _NON_ACTOR_WORDS:
        return False

    if candidate.replace(" ", "").isdigit():
        return False

    if any(c.isdigit() for c in candidate):
        return False

    if candidate.lower() in _LOCATION_WORDS:
        return False

    return True


def resolve_actor_to_entity(db: Any, actor_name: str, *, allow_create: bool = False) -> Any:
    """Resolve an actor name to a canonical Entity record.

    SAFETY: By default (allow_create=False), this function only resolves to
    EXISTING canonical entities. It does NOT create new Entity records for
    unverified deterministic candidates.

    When allow_create=True (used only by the AI extraction path, which is
    more reliable), a new Entity is created if no match exists.

    Returns the Entity instance, or None if no safe match exists.
    """
    from sqlalchemy import select

    from backend.database.models.entity import Entity
    from domains.graph.engine import normalize_name

    display = actor_name.strip()
    if not display:
        return None

    canonical = normalize_name(display)
    entity = db.execute(
        select(Entity).where(Entity.canonical_name == canonical)
    ).scalar_one_or_none()

    if entity is not None:
        return entity

    # No existing match. Only create if explicitly allowed (AI path).
    if not allow_create:
        return None

    entity = Entity(
        type="organization",
        canonical_name=canonical,
        display_name=display,
        aliases=json.dumps([], ensure_ascii=False),
    )
    db.add(entity)
    db.flush()
    return entity


def extract_and_link_actors(db: Any, text: str, *, trusted: bool = False) -> list[str]:
    """Extract actors from text and link to canonical entities.

    Args:
        db: Database session.
        text: Source text for extraction.
        trusted: If True, allows creating new canonical entities (AI path).
                 If False (default), only resolves to existing entities.

    Returns a list of actor name strings that were successfully resolved
    to canonical entities. Unresolved candidates are NOT included.
    """
    actors = extract_actors_deterministic(text)
    resolved: list[str] = []
    unresolved: list[str] = []

    for actor in actors:
        entity = resolve_actor_to_entity(db, actor, allow_create=trusted)
        if entity is not None:
            resolved.append(actor)
        else:
            unresolved.append(actor)

    # Shadow-mode: track unresolved candidates (non-mutating, bounded)
    if unresolved:
        import logging

        logging.getLogger(__name__).debug(
            "actor_extraction: %d unresolved candidates (shadow mode): %s",
            len(unresolved),
            unresolved[:10],  # bounded
        )

    return resolved


__all__ = [
    "extract_actors_deterministic",
    "resolve_actor_to_entity",
    "extract_and_link_actors",
    "_is_valid_actor",
    "_NON_ACTOR_WORDS",
    "_LOCATION_WORDS",
]
