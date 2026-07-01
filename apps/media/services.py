from apps.media.models import Media

def store_private_upload(file_obj) -> Media:
    media = Media.objects.create(
        type=Media.Type.DOCUMENT,
        is_private=True,
        original_name=file_obj.name,
        file=file_obj
    )
    return media
