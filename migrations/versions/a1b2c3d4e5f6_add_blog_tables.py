"""Add blog tables: blog_posts, blog_tags, blog_post_tags

Revision ID: a1b2c3d4e5f6
Revises: 256ba9082e98
Create Date: 2026-05-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '256ba9082e98'
branch_labels = None
depends_on = None


def upgrade():
    # ── blog_tags ─────────────────────────────────────────────────────────────
    op.create_table(
        'blog_tags',
        sa.Column('id',   sa.Integer(), nullable=False),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('slug', sa.String(80), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug'),
    )

    # ── blog_posts ────────────────────────────────────────────────────────────
    op.create_table(
        'blog_posts',
        sa.Column('id',              sa.Integer(),               nullable=False),
        sa.Column('slug',            sa.String(220),             nullable=False),
        sa.Column('title',           sa.String(300),             nullable=False),
        sa.Column('seo_title',       sa.String(70),              nullable=True),
        sa.Column('seo_description', sa.String(165),             nullable=True),
        sa.Column('content_md',      sa.Text(),                  nullable=False, server_default=''),
        sa.Column('content_html',    sa.Text(),                  nullable=True),
        sa.Column('category',        sa.String(20),              nullable=False, server_default='evergreen'),
        sa.Column('source_url',      sa.String(500),             nullable=True),
        sa.Column('source_name',     sa.String(120),             nullable=True),
        sa.Column('is_published',    sa.Boolean(),               nullable=False, server_default='false'),
        sa.Column('published_at',    sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at',      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('reading_time_min', sa.Integer(),              nullable=True, server_default='5'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_blog_posts_slug',         'blog_posts', ['slug'],         unique=True)
    op.create_index('ix_blog_posts_is_published', 'blog_posts', ['is_published'], unique=False)
    op.create_index('ix_blog_posts_published_at', 'blog_posts', ['published_at'], unique=False)

    # ── blog_post_tags (M2M) ──────────────────────────────────────────────────
    op.create_table(
        'blog_post_tags',
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('tag_id',  sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['blog_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'],  ['blog_tags.id'],  ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('post_id', 'tag_id'),
    )


def downgrade():
    op.drop_table('blog_post_tags')
    op.drop_index('ix_blog_posts_published_at', table_name='blog_posts')
    op.drop_index('ix_blog_posts_is_published', table_name='blog_posts')
    op.drop_index('ix_blog_posts_slug',         table_name='blog_posts')
    op.drop_table('blog_posts')
    op.drop_table('blog_tags')
