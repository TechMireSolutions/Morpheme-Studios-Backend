from __future__ import annotations

import pytest

from apps.blog.models import BlogPost
from apps.core.sanitize import sanitize_html

pytestmark = pytest.mark.django_db


def _make(body: str) -> BlogPost:
    return BlogPost.objects.create(slug="p", title="P", body=body)


# --- script / dangerous content removed ---
def test_script_tag_removed():
    post = _make("<p>hi</p><script>alert('xss')</script>")
    assert "<script" not in post.body
    assert "alert(" not in post.body
    assert "<p>hi</p>" in post.body


def test_event_handler_attribute_removed():
    post = _make('<img src="x" onerror="alert(1)">')
    assert "onerror" not in post.body
    assert "alert(1)" not in post.body


def test_javascript_url_removed():
    post = _make('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in post.body


def test_iframe_and_style_removed():
    post = _make('<iframe src="evil"></iframe><style>body{}</style><svg onload=alert(1)></svg>')
    assert "<iframe" not in post.body
    assert "<style" not in post.body
    assert "onload" not in post.body


def test_disallowed_tag_stripped_but_text_kept():
    post = _make("<form><input>keep this text</form>")
    assert "<form" not in post.body and "<input" not in post.body
    assert "keep this text" in post.body


# --- allowed formatting preserved ---
def test_allowed_formatting_preserved():
    html = ("<h2>Title</h2><p><strong>bold</strong> and <em>italic</em></p>"
            "<ul><li>one</li><li>two</li></ul><blockquote>quote</blockquote>"
            "<pre><code>code</code></pre>")
    post = _make(html)
    for frag in ("<h2>", "<strong>", "<em>", "<ul>", "<li>", "<blockquote>", "<code>"):
        assert frag in post.body


def test_safe_link_preserved_with_rel():
    post = _make('<a href="https://example.com">link</a>')
    assert 'href="https://example.com"' in post.body
    assert "rel=" in post.body  # nh3 adds safe rel


def test_safe_image_preserved():
    post = _make('<img src="https://cdn.example.com/x.jpg" alt="x">')
    assert 'src="https://cdn.example.com/x.jpg"' in post.body
    assert 'alt="x"' in post.body


# --- helper direct ---
def test_sanitize_html_empty_input():
    assert sanitize_html(None) == ""
    assert sanitize_html("") == ""
