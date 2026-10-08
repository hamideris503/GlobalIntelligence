"""Entity و EntityRelationship — پایه‌ی Knowledge Graph (بند 26)."""
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin
from backend.database.enums import EntityType, RelationType


class Entity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("type", "canonical_name", name="uq_entity_type_name"),)

    type: Mapped[str] = mapped_column(String(32), default=EntityType.other.value, index=True)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(512))
    aliases: Mapped[str | None] = mapped_column(Text)  # JSON list
    country: Mapped[str | None] = mapped_column(String(2))
    description: Mapped[str | None] = mapped_column(Text)

    # اگر Entity همان Source/Country/Asset باشد، ارجاع اختیاری
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )

    outgoing: Mapped[list[EntityRelationship]] = relationship(
        foreign_keys="EntityRelationship.from_entity_id",
        back_populates="from_entity",
        cascade="all, delete-orphan",
    )
    incoming: Mapped[list[EntityRelationship]] = relationship(
        foreign_keys="EntityRelationship.to_entity_id",
        back_populates="to_entity",
        cascade="all, delete-orphan",
    )


class EntityRelationship(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "entity_relationships"

    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relation: Mapped[str] = mapped_column(String(32), default=RelationType.other.value)
    weight: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    valid_from: Mapped[str | None] = mapped_column(String(64))
    valid_to: Mapped[str | None] = mapped_column(String(64))
    evidence: Mapped[str | None] = mapped_column(Text)

    from_entity: Mapped[Entity] = relationship(
        foreign_keys=[from_entity_id], back_populates="outgoing"
    )
    to_entity: Mapped[Entity] = relationship(
        foreign_keys=[to_entity_id], back_populates="incoming"
    )
