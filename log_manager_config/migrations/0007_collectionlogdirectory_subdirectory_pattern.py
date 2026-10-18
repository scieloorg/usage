from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "log_manager_config",
            "0006_logmanagercollectionconfig_opensearch_index_policy",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="collectionlogdirectory",
            name="subdirectory_pattern",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional pattern relative to Path, such as */*/preprints-scielo-org. Leave blank to scan the entire directory.",
                max_length=255,
                verbose_name="Subdirectory Pattern",
            ),
        ),
    ]
