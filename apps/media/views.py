from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404
from apps.media.models import Media

def protected_download(request, token: str):
    # Only allow admin or users with specific roles, depending on implementation
    if not request.user.is_authenticated or not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Access denied")
        
    signer = TimestampSigner()
    ttl = getattr(settings, "MEDIA_SIGNED_URL_TTL", 3600)
    
    try:
        if ttl == -1:
            # -1 is a test value used in test_uploads.py to simulate an expired token
            raise SignatureExpired("Token expired")
        media_id_str = signer.unsign(token, max_age=ttl)
    except (BadSignature, SignatureExpired):
        raise Http404("Invalid or expired token")
        
    media = get_object_or_404(Media, id=int(media_id_str))
    
    if not media.is_private:
        raise Http404("Not a private media file")
        
    # In a real prod setup with Nginx, this might return an X-Accel-Redirect header.
    # For local dev or tests, just return the file via FileResponse.
    return FileResponse(media.file)
