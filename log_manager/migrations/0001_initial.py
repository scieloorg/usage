# Generated by Django 4.2.7 on 2024-04-12 19:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("collection", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LogFile",
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
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last update date"
                    ),
                ),
                (
                    "hash",
                    models.CharField(
                        blank=True,
                        max_length=32,
                        null=True,
                        unique=True,
                        verbose_name="Hash MD5",
                    ),
                ),
                ("path", models.CharField(max_length=255, verbose_name="Name")),
                ("stat_result", models.JSONField(verbose_name="OS Stat Result")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CRE", "Created"),
                            ("QUE", "Queued"),
                            ("PAR", "Parsing"),
                            ("PRO", "Processed"),
                            ("INV", "Invalidated"),
                        ],
                        max_length=3,
                        verbose_name="Status",
                    ),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="collection.collection",
                        verbose_name="Collection",
                    ),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_creator",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creator",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_mod_user",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updater",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log File",
                "verbose_name_plural": "Log Files",
            },
        ),
        migrations.CreateModel(
            name="LogProcessedRow",
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
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last update date"
                    ),
                ),
                ("server_time", models.DateTimeField(verbose_name="Server Time")),
                ("browser_name", models.CharField(verbose_name="Browser Name")),
                ("browser_version", models.CharField(verbose_name="Browser Version")),
                ("ip", models.CharField(verbose_name="IP")),
                ("latitude", models.FloatField(verbose_name="Latitude")),
                ("longitude", models.FloatField(verbose_name="Longitude")),
                ("action_name", models.CharField(verbose_name="Action Name")),
                (
                    "creator",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_creator",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creator",
                    ),
                ),
                (
                    "log_file",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="log_manager.logfile",
                        verbose_name="LogFile",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_mod_user",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updater",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log Processed Row",
                "verbose_name_plural": "Log Processed Rows",
                "indexes": [
                    models.Index(
                        fields=["server_time"], name="log_manager_server__3149e9_idx"
                    ),
                    models.Index(
                        fields=["browser_name"], name="log_manager_browser_7f7496_idx"
                    ),
                    models.Index(
                        fields=["browser_version"],
                        name="log_manager_browser_54ac66_idx",
                    ),
                    models.Index(fields=["ip"], name="log_manager_ip_8ca66d_idx"),
                    models.Index(
                        fields=["latitude"], name="log_manager_latitud_dd27d0_idx"
                    ),
                    models.Index(
                        fields=["longitude"], name="log_manager_longitu_0fae10_idx"
                    ),
                    models.Index(
                        fields=["action_name"], name="log_manager_action__76b1de_idx"
                    ),
                ],
                "unique_together": {
                    (
                        "server_time",
                        "browser_name",
                        "browser_version",
                        "ip",
                        "latitude",
                        "longitude",
                        "action_name",
                    )
                },
            },
        ),
        migrations.CreateModel(
            name="LogFileDate",
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
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last update date"
                    ),
                ),
                ("date", models.DateField(verbose_name="Date")),
                (
                    "creator",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_creator",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creator",
                    ),
                ),
                (
                    "log_file",
                    models.ForeignKey(
                        blank=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="log_manager.logfile",
                        verbose_name="Log File",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_mod_user",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updater",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log File Date",
                "verbose_name_plural": "Log File Dates",
                "ordering": ["-date"],
                "unique_together": {("date", "log_file")},
            },
        ),
        migrations.CreateModel(
            name="CollectionConfig",
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
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last update date"
                    ),
                ),
                (
                    "config_type",
                    models.CharField(
                        choices=[
                            ("LOG", "Logs"),
                            ("PRO", "Processed Data"),
                            ("MTS", "Metrics"),
                            ("DAY", "Files per Day"),
                        ],
                        max_length=3,
                        verbose_name="Type",
                    ),
                ),
                ("value", models.CharField(max_length=255, verbose_name="Value")),
                (
                    "is_enabled",
                    models.BooleanField(default=True, verbose_name="Enabled"),
                ),
                ("start_date", models.DateField(verbose_name="Start Date")),
                (
                    "end_date",
                    models.DateField(blank=True, null=True, verbose_name="End Date"),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="collection.collection",
                        verbose_name="Collection",
                    ),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_creator",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creator",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_mod_user",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updater",
                    ),
                ),
            ],
            options={
                "verbose_name": "Collection Configuration",
                "verbose_name_plural": "Collection Configurations",
                "ordering": ["collection", "value"],
                "unique_together": {("config_type", "value")},
            },
        ),
        migrations.CreateModel(
            name="ApplicationConfig",
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
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last update date"
                    ),
                ),
                (
                    "config_type",
                    models.CharField(
                        choices=[
                            ("SUP", "Supplies Directory"),
                            ("GEO", "Supply Geolocation Map Path"),
                            ("ROB", "Supply Counter Robots Path"),
                            ("ACR", "Dictionary ISSN-ACRONYM Path"),
                            ("DAT", "Dictionary PID-DATES Path"),
                            ("ISS", "Dictionary PID-ISSN Path"),
                            ("LAN", "Dictionary PID-FORMAT-LANG Path"),
                            ("PDF", "Dictionary PDF-PID Path"),
                            ("LFF", "Log File Supported Format"),
                        ],
                        max_length=3,
                        verbose_name="Config Type",
                    ),
                ),
                ("value", models.CharField(max_length=255, verbose_name="Value")),
                (
                    "is_enabled",
                    models.BooleanField(default=True, verbose_name="Enabled"),
                ),
                ("version_number", models.IntegerField(verbose_name="Version Number")),
                (
                    "creator",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_creator",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creator",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_mod_user",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updater",
                    ),
                ),
            ],
            options={
                "verbose_name": "Application Config",
                "verbose_name_plural": "Application Configs",
                "ordering": ["value"],
                "unique_together": {("config_type", "value", "version_number")},
            },
        ),
    ]
