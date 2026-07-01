import os
import uuid
from django.db import models
from django.conf import settings

def media_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join("uploads" if not instance.is_private else "private_uploads", filename)

class Media(models.Model):
    class Type(models.TextChoices):
        IMAGE = "IMAGE", "Image"
        VIDEO = "VIDEO", "Video"
        DOCUMENT = "DOCUMENT", "Document"

    type = models.CharField(max_length=20, choices=Type.choices, default=Type.IMAGE)
    is_private = models.BooleanField(default=False)
    original_name = models.CharField(max_length=255)
    alt_text = models.CharField(max_length=255, blank=True)
    mime = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to=media_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Media"

    def __str__(self):
        return self.original_name
