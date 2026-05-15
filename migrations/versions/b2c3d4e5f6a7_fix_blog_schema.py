"""Fix blog tables schema: move from public → nis2_compliance

Previous migration (a1b2c3d4e5f6) created blog tables without schema awareness.
This migration:
  1. Drops the wrongly-placed tables from public (if they exist there)
  2. Creates the tables in the correct schema (DB_SCHEMA env var, e.g. nis2_compliance)
     using IF NOT EXISTS logic so it's idempotent.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-15 18:00:00.000000
"""
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

_SCHEMA = os.environ.get('DB_SCHEMA') or None


def _table_exists(conn, table_name: str, schema: str | None = None) -> bool:
    """Check if a table exists in the given schema (or public)."""
    schema_check = f"= '{schema}'" if schema else "= 'public'"
    result = conn.execute(text(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema {schema_check}
            AND table_name = :tname
        )
    """), {'tname': table_name})
    return result.scalar()


def _tbl(name: str) -> str:
    return f'{_SCHEMA}.{name}' if _SCHEMA else name


def upgrade():
    conn = op.get_bind()

    # ── Step 1: drop incorrectly-placed tables in public schema ──────────────
    if _SCHEMA:
        # Only clean up if we're running with a target schema
        # (no-op if they were never created in public)
        conn.execute(text('DROP TABLE IF EXISTS public.blog_post_tags CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS public.blog_posts CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS public.blog_tags CASCADE'))

    # ── Step 2: create tables in correct schema if they don't exist yet ──────
    if not _table_exists(conn, 'blog_tags', _SCHEMA):
        op.create_table(
            'blog_tags',
            sa.Column('id',   sa.Integer(), nullable=False),
            sa.Column('name', sa.String(60), nullable=False),
            sa.Column('slug', sa.String(80), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('slug'),
            schema=_SCHEMA,
        )

    if not _table_exists(conn, 'blog_posts', _SCHEMA):
        op.create_table(
            'blog_posts',
            sa.Column('id',               sa.Integer(),               nullable=False),
            sa.Column('slug',             sa.String(220),             nullable=False),
            sa.Column('title',            sa.String(300),             nullable=False),
            sa.Column('seo_title',        sa.String(70),              nullable=True),
            sa.Column('seo_description',  sa.String(165),             nullable=True),
            sa.Column('content_md',       sa.Text(),                  nullable=False,
                      server_default=''),
            sa.Column('content_html',     sa.Text(),                  nullable=True),
            sa.Column('category',         sa.String(20),              nullable=False,
                      server_default='evergreen'),
            sa.Column('source_url',       sa.String(500),             nullable=True),
            sa.Column('source_name',      sa.String(120),             nullable=True),
            sa.Column('is_published',     sa.Boolean(),               nullable=False,
                      server_default='false'),
            sa.Column('published_at',     sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('reading_time_min', sa.Integer(),               nullable=True,
                      server_default='5'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug'),
            schema=_SCHEMA,
        )
        op.create_index('ix_blog_posts_slug',         'blog_posts', ['slug'],
                        unique=True,  schema=_SCHEMA)
        op.create_index('ix_blog_posts_is_published', 'blog_posts', ['is_published'],
                        unique=False, schema=_SCHEMA)
        op.create_index('ix_blog_posts_published_at', 'blog_posts', ['published_at'],
                        unique=False, schema=_SCHEMA)

    if not _table_exists(conn, 'blog_post_tags', _SCHEMA):
        op.create_table(
            'blog_post_tags',
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('tag_id',  sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ['post_id'], [_tbl('blog_posts') + '.id'], ondelete='CASCADE'
            ),
            sa.ForeignKeyConstraint(
                ['tag_id'], [_tbl('blog_tags') + '.id'], ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('post_id', 'tag_id'),
            schema=_SCHEMA,
        )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'blog_post_tags', _SCHEMA):
        op.drop_table('blog_post_tags', schema=_SCHEMA)
    if _table_exists(conn, 'blog_posts', _SCHEMA):
        op.drop_index('ix_blog_posts_published_at', table_name='blog_posts', schema=_SCHEMA)
        op.drop_index('ix_blog_posts_is_published', table_name='blog_posts', schema=_SCHEMA)
        op.drop_index('ix_blog_posts_slug',         table_name='blog_posts', schema=_SCHEMA)
        op.drop_table('blog_posts', schema=_SCHEMA)
    if _table_exists(conn, 'blog_tags', _SCHEMA):
        op.drop_table('blog_tags', schema=_SCHEMA)
