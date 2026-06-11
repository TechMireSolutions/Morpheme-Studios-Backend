from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect
from apps.core.models import RedirectRule


class RedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        
        # Query active redirect rules
        rule = RedirectRule.objects.filter(from_path=path, is_active=True).first()
        if not rule:
            # Try matching without trailing slash if path ends with it
            if path.endswith('/') and len(path) > 1:
                rule = RedirectRule.objects.filter(from_path=path[:-1], is_active=True).first()
            # Try matching with trailing slash if path doesn't end with it
            elif not path.endswith('/'):
                rule = RedirectRule.objects.filter(from_path=path + '/', is_active=True).first()

        if rule:
            if rule.status_code == 301:
                return HttpResponsePermanentRedirect(rule.to_path)
            elif rule.status_code == 302:
                return HttpResponseRedirect(rule.to_path)

        return self.get_response(request)
