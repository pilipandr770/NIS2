"""
Blog public routes:
  GET /blog/               → paginated article list
  GET /blog/<slug>         → single article
  GET /blog/tag/<tag-slug> → articles by tag
  GET /blog/feed.xml       → RSS 2.0 feed
"""

from datetime import UTC, datetime

from flask import abort, render_template, request, make_response

from blog import blog_bp
from blog.models import BlogPost, BlogTag

_PER_PAGE = 12


@blog_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')

    query = BlogPost.query.filter_by(is_published=True)
    if category in ('news', 'evergreen'):
        query = query.filter_by(category=category)

    pagination = (
        query
        .order_by(BlogPost.published_at.desc())
        .paginate(page=page, per_page=_PER_PAGE, error_out=False)
    )

    # Sidebar: all tags with at least one published post
    popular_tags = (
        BlogTag.query
        .join(BlogTag.posts)
        .filter(BlogPost.is_published == True)
        .distinct()
        .order_by(BlogTag.name)
        .limit(30)
        .all()
    )

    # Latest 3 for sidebar "recent" widget
    recent_posts = (
        BlogPost.query
        .filter_by(is_published=True)
        .order_by(BlogPost.published_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'blog/index.html',
        pagination=pagination,
        posts=pagination.items,
        popular_tags=popular_tags,
        recent_posts=recent_posts,
        active_category=category,
    )


@blog_bp.route('/<slug>')
def article(slug):
    post = BlogPost.query.filter_by(slug=slug, is_published=True).first_or_404()

    # Related: same tags, exclude self, max 3
    related = []
    if post.tags:
        tag_ids = [t.id for t in post.tags]
        related = (
            BlogPost.query
            .filter(
                BlogPost.is_published == True,
                BlogPost.id != post.id,
                BlogPost.tags.any(BlogTag.id.in_(tag_ids)),
            )
            .order_by(BlogPost.published_at.desc())
            .limit(3)
            .all()
        )

    return render_template('blog/article.html', post=post, related=related)


@blog_bp.route('/tag/<tag_slug>')
def tag(tag_slug):
    blog_tag = BlogTag.query.filter_by(slug=tag_slug).first_or_404()
    page = request.args.get('page', 1, type=int)

    pagination = (
        blog_tag.posts
        .filter(BlogPost.is_published == True)
        .order_by(BlogPost.published_at.desc())
        .paginate(page=page, per_page=_PER_PAGE, error_out=False)
    )

    return render_template(
        'blog/tag.html',
        tag=blog_tag,
        pagination=pagination,
        posts=pagination.items,
    )


@blog_bp.route('/feed.xml')
def feed():
    posts = (
        BlogPost.query
        .filter_by(is_published=True)
        .order_by(BlogPost.published_at.desc())
        .limit(20)
        .all()
    )

    now_rfc = _rfc2822(datetime.now(UTC))

    items_xml = ''
    for p in posts:
        pub_date = _rfc2822(p.published_at) if p.published_at else now_rfc
        desc = (p.seo_description or p.title or '')
        items_xml += f"""
  <item>
    <title><![CDATA[{p.title}]]></title>
    <link>https://nis2.store/blog/{p.slug}</link>
    <guid isPermaLink="true">https://nis2.store/blog/{p.slug}</guid>
    <pubDate>{pub_date}</pubDate>
    <description><![CDATA[{desc}]]></description>
    {''.join(f'<category>{t.name}</category>' for t in p.tags)}
  </item>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>NIS2 Compliance Blog — Cybersicherheit &amp; NIS2 für Deutschland</title>
  <link>https://nis2.store/blog/</link>
  <description>Aktuelle Cybersicherheitsnews und NIS2-Ratgeber für deutsche Unternehmen</description>
  <language>de</language>
  <lastBuildDate>{now_rfc}</lastBuildDate>
  <atom:link href="https://nis2.store/blog/feed.xml" rel="self" type="application/rss+xml"/>
{items_xml}
</channel>
</rss>"""

    response = make_response(xml)
    response.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
    return response


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rfc2822(dt: datetime) -> str:
    from email.utils import format_datetime
    return format_datetime(dt)
