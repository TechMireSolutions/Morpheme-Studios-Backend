from django.core.signing import TimestampSigner

def make_token(media_id: int) -> str:
    signer = TimestampSigner()
    return signer.sign(str(media_id))
