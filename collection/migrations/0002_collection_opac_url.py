from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("collection", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="opac_url",
            field=models.URLField(
                "OPAC URL",
                blank=True,
                max_length=500,
                null=True,
            ),
        ),
    ]
