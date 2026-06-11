"""Server-side HTML sanitization for stored rich text (defense against stored
XSS). Uses nh3 (Rust ammonia bindings) with a strict allowlist — not a denylist,
and not reliant on CSP. Applied at write time so the stored value is always safe.
"""
from __future__ import annotations

import nh3

# Formatting needed for blog articles — headings, lists, links, emphasis,
# quotes, code, images. Everything else (script, style, iframe, object, form,
# event handlers, etc.) is stripped.
ALLOWED_TAGS: set[str] = {
    "p", "br", "hr", "span", "div",
    "strong", "b", "em", "i", "u", "s", "sub", "sup",
    "blockquote", "code", "pre",
    "ul", "ol", "li",
    "h2", "h3", "h4", "h5",
    "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tr", "th", "td",
}

ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    # NB: do not list "rel" here — nh3 manages it via `link_rel` below.
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "span": {"class"},
    "div": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}


def sanitize_html(html: str | None) -> str:
    """Return a sanitized copy of `html`. nh3 drops disallowed tags/attributes,
    strips javascript:/data: URLs, removes event-handler attributes, and forces
    safe rel on links."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )
