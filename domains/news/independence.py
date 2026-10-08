"""Source Independence Engine (Phase 14).

مسئله: «تعداد mention ≠ تعداد تأیید مستقل». اگر BBC و یک بازنشرِ BBC هر دو یک
خبر را پوشش دهند، این یک تأیید است نه دو. این موتور:

1. گراف وابستگی منابع را می‌سازد (یال‌های ثبت‌شده + heuristic همان دامنه/aggregator).
2. منابع وابسته را با Union-Find به یک «منبع مستقل» فرو می‌کاست (نماینده = با
   بالاترین credibility، سپس independence).
3. برای هر Claim، منابع ذکرشده را از مقالات Event جمع می‌کند و:
   - `supporting_source_count` = تعداد کل منابع (mention)
   - `independent_source_count` = تعداد منابع مستقل
   - `source_independence` = independent / supporting
4. `verification_status` را اصلاح می‌کند: `corroborated` فقط با ≥۲ منبع مستقل
   (نه صرفاً ≥۲ mention).

Deterministic است (بدون AI، بدون وابستگی خارجی).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.enums import VerificationStatus
from backend.database.models.claim import Claim
from backend.database.models.source import Source
from backend.database.models.source_dependency import SourceDependency

logger = get_logger(__name__)

# آستانه‌ی نسبت استقلال برای اینکه یک Claim «مستقل تأییدشده» تلقی شود
INDEPENDENCE_CORROBORATION_THRESHOLD = 0.5


@dataclass
class IndependenceOutcome:
    sources: int = 0
    dependency_edges: int = 0
    groups: int = 0
    claims_processed: int = 0
    claims_with_sources: int = 0
    corroborated: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "sources": self.sources,
            "dependency_edges": self.dependency_edges,
            "groups": self.groups,
            "claims_processed": self.claims_processed,
            "claims_with_sources": self.claims_with_sources,
            "corroborated": self.corroborated,
            "failed": self.failed,
            "errors": self.errors,
        }


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx


def _load_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


def _parse_id_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if x]


class SourceDependencyService:
    """CRUD روی یال‌های وابستگی منابع (Phase 14)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, *, limit: int = 500) -> list[SourceDependency]:
        stmt = (
            select(SourceDependency)
            .order_by(SourceDependency.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def add(
        self,
        source_id: uuid.UUID,
        depends_on_id: uuid.UUID,
        *,
        kind: str = "manual",
        weight: float = 1.0,
        detected_by: str = "manual",
    ) -> SourceDependency:
        existing = self.db.execute(
            select(SourceDependency).where(
                SourceDependency.source_id == source_id,
                SourceDependency.depends_on_id == depends_on_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        dep = SourceDependency(
            source_id=source_id,
            depends_on_id=depends_on_id,
            kind=kind,
            weight=max(0.0, min(1.0, float(weight))),
            detected_by=detected_by,
        )
        self.db.add(dep)
        self.db.commit()
        self.db.refresh(dep)
        return dep

    def delete(self, dependency_id: uuid.UUID) -> bool:
        dep = self.db.get(SourceDependency, dependency_id)
        if dep is None:
            return False
        self.db.delete(dep)
        self.db.commit()
        return True


class SourceIndependenceEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- 1) گراف وابستگی ---
    def _canonical_representative(self, members: list[Source]) -> Source:
        """نماینده‌ی یک گروه وابسته: بالاترین credibility، سپس independence، سپس نام."""
        return sorted(
            members,
            key=lambda s: (
                -(s.credibility_score or 0.0),
                -(s.independence_score or 0.0),
                s.name,
            ),
        )[0]

    def build_groups(self) -> tuple[dict[str, str], int, int]:
        """گروه‌های وابستگی را می‌سازد.

        خروجی: (source_id -> representative_id, تعداد منابع, تعداد یال‌ها)
        """
        sources = list(self.db.execute(select(Source)).scalars().all())
        by_id = {str(s.id): s for s in sources}
        uf = _UnionFind()
        for s in sources:
            uf.find(str(s.id))

        edges = 0
        # یال‌های ثبت‌شده
        deps = list(self.db.execute(select(SourceDependency)).scalars().all())
        for dep in deps:
            a, b = str(dep.source_id), str(dep.depends_on_id)
            if a in by_id and b in by_id:
                uf.union(a, b)
                edges += 1

        # heuristic: منابعی که domain مشترک دارند و هم‌نوع‌اند
        # (مثلاً همان سازمان در نوع rss و official) → یک گروه
        by_domain: dict[str, list[str]] = {}
        for s in sources:
            if s.domain:
                by_domain.setdefault(s.domain.lower(), []).append(str(s.id))
        for ids in by_domain.values():
            if len(ids) > 1:
                for other in ids[1:]:
                    if uf.find(ids[0]) != uf.find(other):
                        uf.union(ids[0], other)
                        edges += 1

        # نماینده‌ی هر ریشه
        groups: dict[str, list[str]] = {}
        for sid in by_id:
            groups.setdefault(uf.find(sid), []).append(sid)

        rep_of_root: dict[str, str] = {}
        for root, members in groups.items():
            rep = self._canonical_representative([by_id[m] for m in members])
            rep_of_root[root] = str(rep.id)

        mapping = {sid: rep_of_root[uf.find(sid)] for sid in by_id}
        return mapping, len(sources), edges

    # --- 2) منابع یک Claim از رویداد ---
    def claim_source_ids(self, claim: Claim) -> list[str]:
        """منابع ذکرشده برای یک Claim: منابع اسناد مقالات Event."""
        ids: list[str] = []
        event = claim.event
        if event is not None:
            for article in event.articles:
                doc = article.document
                if doc is not None and doc.source_id is not None:
                    ids.append(str(doc.source_id))
        # منابع صریح ذخیره‌شده روی Claim/Event
        ids.extend(_parse_id_list(claim.sources))
        ids.extend(_parse_id_list(event.sources) if event is not None else [])
        # یکتا و پایدار
        seen: set[str] = set()
        out: list[str] = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def compute_for_claim(
        self, claim: Claim, mapping: dict[str, str]
    ) -> tuple[int, int, float]:
        """(supporting_count, independent_count, independence_ratio)."""
        source_ids = self.claim_source_ids(claim)
        supporting = len(source_ids)
        if supporting == 0:
            return 0, 0, 0.0
        representatives = {mapping.get(sid, sid) for sid in source_ids}
        independent = len(representatives)
        ratio = independent / supporting
        return supporting, independent, round(ratio, 4)

    # --- 3) اجرا ---
    def run(self, *, limit: int = 500) -> IndependenceOutcome:
        outcome = IndependenceOutcome()
        try:
            mapping, n_sources, edges = self.build_groups()
            outcome.sources = n_sources
            outcome.dependency_edges = edges
            outcome.groups = len(set(mapping.values()))
        except Exception as exc:  # noqa: BLE001
            outcome.failed += 1
            outcome.errors.append(f"{type(exc).__name__}: {exc}")
            logger.warning("independence build failed | err=%s", exc)
            return outcome

        stmt = select(Claim).order_by(Claim.created_at.desc()).limit(limit)
        claims = list(self.db.execute(stmt).scalars().all())
        for claim in claims:
            try:
                supporting, independent, ratio = self.compute_for_claim(claim, mapping)
                claim.supporting_source_count = supporting
                claim.independent_source_count = independent
                claim.source_independence = ratio
                outcome.claims_processed += 1
                if supporting > 0:
                    outcome.claims_with_sources += 1

                self._refresh_status(claim)
                if claim.verification_status == VerificationStatus.corroborated.value:
                    outcome.corroborated += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("independence claim failed | claim=%s err=%s", claim.id, exc)
            self.db.commit()

        logger.info("source-independence done | %s", outcome.as_dict())
        return outcome

    def _refresh_status(self, claim: Claim) -> None:
        """status را با درنظر گرفتن استقلال منابع به‌روزرسانی می‌کند.

        supports از تعداد منابع *مستقلِ* ذکرشده می‌آید؛ اگر منبع مستقلی نبود
        ولی Evidence موافق وجود داشت، به سیگنال قبلی (تک‌منبع) برنمی‌گردیم.
        contradicts از Evidence مخالف می‌آید.
        """
        contradicts = sum(1 for e in claim.evidence if e.direction == "contradicts")
        supports = claim.independent_source_count
        if supports == 0:
            supports = sum(1 for e in claim.evidence if e.direction == "supports")

        if supports == 0 and contradicts == 0:
            claim.verification_status = VerificationStatus.unverified.value
        elif supports > 0 and contradicts > 0:
            claim.verification_status = VerificationStatus.disputed.value
        elif supports >= 2 and contradicts == 0:
            claim.verification_status = VerificationStatus.corroborated.value
        elif supports == 1 and contradicts == 0:
            claim.verification_status = VerificationStatus.single_source.value
        elif contradicts > 0 and supports == 0:
            claim.verification_status = VerificationStatus.contradicted.value
        else:
            claim.verification_status = VerificationStatus.unverified.value
