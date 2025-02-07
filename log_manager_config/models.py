from django.db import models
from django.utils.translation import gettext_lazy as _

from collection.models import Collection
from core.models import CommonControlField

from .exceptions import MultipleFilesPerDayForTheSameDateError, UndefinedCollectionFilesPerDayError


class CollectionLogDirectory(CommonControlField):
    collection = models.ForeignKey(
        Collection,
        verbose_name=_('Collection'),
        on_delete=models.DO_NOTHING,
    )
    directory_name = models.CharField(
        verbose_name=_('Directory Name'),
        max_length=255, 
        unique=True,
        blank=True,
        null=True,
    )
    path = models.CharField(
        verbose_name=_('Path'),
        max_length=255, 
        unique=True, 
        blank=False, 
        null=False,
    )
    active = models.BooleanField(
        verbose_name=_('Active'),
        default=True,
    )

    def __str__(self):
        return f'{self.path} - {self.directory_name}'
    
    class Meta:
        unique_together = ('collection', 'path')


class CollectionLogFilesPerDay(CommonControlField):
    collection = models.ForeignKey(
        Collection,
        verbose_name=_('Collection'),
        on_delete=models.DO_NOTHING,
    )
    start_date = models.DateField(
        verbose_name=_('Start Date'),
        blank=False,
        null=False,
    )
    end_date = models.DateField(
        verbose_name=_('End Date'),
        blank=True,
        null=True,
    )
    quantity = models.IntegerField(
        verbose_name=_('Quantity'),
        default=1,
    )

    def __str__(self):
        return f'{self.start_date} - {self.quantity}'
    
    @classmethod
    def get_number_of_expected_files_by_day(cls, collection_acron2, date):
        files_by_day = cls.objects.filter(
            models.Q(collection__acron2=collection_acron2) &
            models.Q(start_date__lte=date) &
            (models.Q(end_date__gte=date) | models.Q(end_date__isnull=True))
        )

        if files_by_day.count() > 1:
            raise MultipleFilesPerDayForTheSameDateError(_("ERROR. Please, set the field end_date for the collection {collection_acron2}."))

        if files_by_day.count() == 0:
            raise UndefinedCollectionFilesPerDayError(_("ERROR. Please, set the number of files per day for the collection {collection_acron2}."))
        
        return int(files_by_day.get().value)
    
    class Meta:
        unique_together = ('collection', 'start_date', 'quantity', )


class CollectionEmail(CommonControlField):
    collection = models.ForeignKey(
        Collection,
        verbose_name=_('Collection'),
        on_delete=models.DO_NOTHING,
    )
    name = models.CharField(
        verbose_name=_('Name'),
        max_length=255, 
        blank=True,
        null=True,
    )
    position = models.CharField(
        verbose_name=_('Position'),
        max_length=255, 
        blank=True,
        null=True,
    )
    email = models.EmailField(
        verbose_name=_('E-mail'),
        blank=False,
        null=False,
    )
    active = models.BooleanField(
        verbose_name=_('Active'),
        default=True,
    )

    def __str__(self):
        return f'{self.email} - {self.name}'
    
    class Meta:
        unique_together = ('collection', 'email')


class SupportedLogFile(CommonControlField):
    file_extension = models.CharField(
        verbose_name=_('File Extension'),
        max_length=255, 
        unique=True,
        blank=False,
        null=False,
    )
    description = models.TextField(
        verbose_name=_('Description'),
        blank=True,
        null=True,
    )

    def __str__(self):
        return f'{self.file_extension}'
