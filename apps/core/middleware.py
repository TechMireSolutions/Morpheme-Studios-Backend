"""Runtime redirects driven by the editable RedirectRule table (architecture §9).

Matches the incoming path against active rules and issues a 301/302 before the
view runs — so editors can fix old WordPress URLs without code/Nginx changes.
Rules are cached briefly to avoid a DB hit on every request, and app routes
(api/admin/media) are skipped so redirects never shadow the application.
"""
from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect

_CACHE_KEY = "core:redirect_rules"
_CACHE_TTL = 60  # seconds


def _rules() -> dict[str, tuple[str, int]]:
    rules = cache.get(_CACHE_KEY)
    if rules is None:
        from apps.core.models import RedirectRule
        rules = {
            r.from_path: (r.to_path, r.status_code)
            for r in RedirectRule.objects.filter(is_active=True).only(
                "from_path", "to_path", "status_code")
        }
        cache.set(_CACHE_KEY, rules, _CACHE_TTL)
    return rules


class RedirectMiddleware:
    SKIP_PREFIXES = ("/admin", "/api", "/media", "/static", "/protected", "/_protected")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith(self.SKIP_PREFIXES):
            rules = _rules()
            match = rules.get(path) or rules.get(path.rstrip("/")) or rules.get(path + "/")
            if match:
                to_path, code = match
                cls = HttpResponsePermanentRedirect if code == 301 else HttpResponseRedirect
                return cls(to_path)
        return self.get_response(request)
