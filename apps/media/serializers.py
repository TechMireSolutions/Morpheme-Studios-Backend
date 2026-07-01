from rest_framework import serializers
from apps.media.models import Media

class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = ['id', 'type', 'is_private', 'original_name', 'alt_text', 'file', 'created_at']
