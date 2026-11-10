from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(UTC)


item_tags = Table(
    "item_tags",
    Base.metadata,
    Column("item_id", ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class BricksetSet(Base):
    """Cached Brickset record. Fetched once, then served from here."""

    __tablename__ = "brickset_sets"

    set_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Brickset setID
    number: Mapped[str] = mapped_column(String, index=True)  # e.g. "75159"
    number_variant: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer)
    theme: Mapped[str | None] = mapped_column(String, index=True)
    subtheme: Mapped[str | None] = mapped_column(String)
    pieces: Mapped[int | None] = mapped_column(Integer)
    minifigs: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String)
    thumbnail_url: Mapped[str | None] = mapped_column(String)
    brickset_url: Mapped[str | None] = mapped_column(String)
    raw: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def full_number(self) -> str:
        return f"{self.number}-{self.number_variant}"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String, index=True)  # "set" | "other"
    box: Mapped[str] = mapped_column(String, default="", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    # type == "set"
    brickset_set_id: Mapped[int | None] = mapped_column(ForeignKey("brickset_sets.set_id"))
    # type == "other"
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    brickset_set: Mapped[BricksetSet | None] = relationship(lazy="joined")
    tags: Mapped[list[Tag]] = relationship(secondary=item_tags, lazy="selectin")
