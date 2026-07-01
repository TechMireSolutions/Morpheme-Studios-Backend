from django.db import migrations, models
import apps.media.models

class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Media',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('IMAGE', 'Image'), ('VIDEO', 'Video'), ('DOCUMENT', 'Document')], default='IMAGE', max_length=20)),
                ('is_private', models.BooleanField(default=False)),
                ('original_name', models.CharField(max_length=255)),
                ('alt_text', models.CharField(blank=True, max_length=255)),
                ('file', models.FileField(upload_to=apps.media.models.media_upload_path)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': 'Media',
            },
        ),
    ]
