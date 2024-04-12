# Generated by Django 4.2.7 on 2024-04-12 19:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Collection",
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
                    "acron3",
                    models.CharField(
                        blank=True,
                        max_length=10,
                        null=True,
                        verbose_name="Acronym with 3 chars",
                    ),
                ),
                (
                    "acron2",
                    models.CharField(
                        blank=True,
                        max_length=10,
                        null=True,
                        verbose_name="Acronym with 2 chars",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        blank=True, max_length=10, null=True, verbose_name="Código"
                    ),
                ),
                (
                    "domain",
                    models.URLField(blank=True, null=True, verbose_name="Domain"),
                ),
                (
                    "main_name",
                    models.TextField(blank=True, null=True, verbose_name="Main name"),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("certified", "Certified"),
                            ("development", "Development"),
                            ("diffusion", "Diffusion"),
                            ("independent", "Independent"),
                        ],
                        max_length=20,
                        null=True,
                        verbose_name="Status",
                    ),
                ),
                (
                    "has_analytics",
                    models.BooleanField(
                        blank=True, null=True, verbose_name="Has analytics"
                    ),
                ),
                (
                    "collection_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("journals", "Journals"),
                            ("preprints", "Preprints"),
                            ("repositories", "Repositories"),
                            ("books", "Books"),
                            ("data", "Data repository"),
                        ],
                        max_length=20,
                        null=True,
                        verbose_name="Collection Type",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        blank=True, null=True, verbose_name="Is active"
                    ),
                ),
                (
                    "foundation_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Foundation data"
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
                "verbose_name": "Coleção",
                "verbose_name_plural": "Coleções",
                "ordering": ["main_name"],
            },
        ),
        migrations.CreateModel(
            name="CollectionName",
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
                ("text", models.TextField(blank=True, null=True, verbose_name="Texto")),
                (
                    "collection",
                    modelcluster.fields.ParentalKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="collection_name",
                        to="collection.collection",
                    ),
                ),
                (
                    "language",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.language",
                        verbose_name="Idioma",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(fields=["acron3"], name="collection__acron3_a9f5cf_idx"),
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(fields=["acron2"], name="collection__acron2_a6ae4c_idx"),
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(fields=["code"], name="collection__code_e4f01a_idx"),
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(fields=["domain"], name="collection__domain_f79fa7_idx"),
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(
                fields=["main_name"], name="collection__main_na_f316bd_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(fields=["status"], name="collection__status_ee0d16_idx"),
        ),
        migrations.AddIndex(
            model_name="collection",
            index=models.Index(
                fields=["collection_type"], name="collection__collect_a99863_idx"
            ),
        ),
    ]
