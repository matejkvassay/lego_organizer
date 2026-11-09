"""Baseline: the v0.1 schema, including the FTS5 search index.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Databases created by v0.1 (create_all) already have these tables and no alembic_version row:
    # skip what exists so they are adopted as-is, with their data.
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "brickset_sets" not in existing:
        op.create_table(
            "brickset_sets",
            sa.Column("set_id", sa.Integer, primary_key=True),
            sa.Column("number", sa.String, nullable=False),
            sa.Column("number_variant", sa.Integer, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("year", sa.Integer),
            sa.Column("theme", sa.String),
            sa.Column("subtheme", sa.String),
            sa.Column("pieces", sa.Integer),
            sa.Column("minifigs", sa.Integer),
            sa.Column("image_url", sa.String),
            sa.Column("thumbnail_url", sa.String),
            sa.Column("brickset_url", sa.String),
            sa.Column("raw", sa.JSON),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_brickset_sets_number", "brickset_sets", ["number"])
        op.create_index("ix_brickset_sets_theme", "brickset_sets", ["theme"])

    if "tags" not in existing:
        op.create_table(
            "tags",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False, unique=True),
        )

    if "items" not in existing:
        op.create_table(
            "items",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("type", sa.String, nullable=False),
            sa.Column("box", sa.String, nullable=False),
            sa.Column("notes", sa.Text, nullable=False),
            sa.Column("brickset_set_id", sa.Integer, sa.ForeignKey("brickset_sets.set_id")),
            sa.Column("title", sa.String),
            sa.Column("description", sa.Text),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_items_type", "items", ["type"])
        op.create_index("ix_items_box", "items", ["box"])

    if "item_tags" not in existing:
        op.create_table(
            "item_tags",
            sa.Column("item_id", sa.Integer, sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("tag_id", sa.Integer, sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
        )

    # FTS5 index over the collection; maintained by search.reindex_item.
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS item_fts USING fts5("
        "title, number, theme, subtheme, tags, box, notes, tokenize='unicode61 remove_diacritics 2')"
    )


def downgrade() -> None:
    raise NotImplementedError("The baseline cannot be downgraded: that would delete the whole collection.")
