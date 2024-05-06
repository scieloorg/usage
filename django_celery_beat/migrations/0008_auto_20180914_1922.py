# Generated by Django 2.0.3 on 2018-09-14 19:22
from django.db import migrations, models
from django_celery_beat import validators


class Migration(migrations.Migration):
    dependencies = [
        ('django_celery_beat', '0007_auto_20180521_0826'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crontabschedule',
            name='day_of_month',
            field=models.CharField(
                default='*', max_length=124,
                validators=[validators.day_of_month_validator],
                verbose_name='day of month'
            ),
        ),
        migrations.AlterField(
            model_name='crontabschedule',
            name='day_of_week',
            field=models.CharField(
                default='*', max_length=64,
                validators=[validators.day_of_week_validator],
                verbose_name='day of week'
            ),
        ),
        migrations.AlterField(
            model_name='crontabschedule',
            name='hour',
            field=models.CharField(
                default='*', max_length=96,
                validators=[validators.hour_validator],
                verbose_name='hour'
            ),
        ),
        migrations.AlterField(
            model_name='crontabschedule',
            name='minute',
            field=models.CharField(
                default='*', max_length=240,
                validators=[validators.minute_validator],
                verbose_name='minute'
            ),
        ),
        migrations.AlterField(
            model_name='crontabschedule',
            name='month_of_year',
            field=models.CharField(
                default='*', max_length=64,
                validators=[validators.month_of_year_validator],
                verbose_name='month of year'
            ),
        ),
    ]
