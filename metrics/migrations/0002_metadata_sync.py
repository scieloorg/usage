from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metrics", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="MetadataSyncState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "entity",
                    models.CharField(
                        choices=[("source", "Source"), ("document", "Document")],
                        max_length=16,
                        unique=True,
                    ),
                ),
                ("cursor_updated", models.DateTimeField(blank=True, null=True)),
                ("cursor_pk", models.PositiveBigIntegerField(default=0)),
                ("lease_until", models.DateTimeField(blank=True, null=True)),
                ("heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="MetadataSyncOutbox",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "entity",
                    models.CharField(
                        choices=[("source", "Source"), ("document", "Document")],
                        max_length=16,
                    ),
                ),
                ("object_key", models.CharField(max_length=25)),
                ("payload", models.JSONField()),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["entity", "id"], name="metrics_meta_outbox_entity_idx"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("entity", "object_key"),
                        name="metrics_metadata_outbox_entity_key_uniq",
                    )
                ],
            },
        ),
    ]
