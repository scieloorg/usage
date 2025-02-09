import logging

from django.db import models
from django.utils import timezone
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
    path = models.CharField(
        verbose_name=_('Path'),
        max_length=255, 
        blank=False, 
        null=False,
    )
    directory_name = models.CharField(
        verbose_name=_('Directory Name'),
        max_length=255, 
        blank=True,
        null=True,
    )
    active = models.BooleanField(
        verbose_name=_('Active'),
        default=True,
    )

    def __str__(self):
        return f'{self.collection} - {self.path} - {self.directory_name}'
    
    @classmethod
    def load(cls, data, user):
        for item in data:
            try:
                collection = Collection.objects.get(acron3=item.get('acronym'))
            except Collection.DoesNotExist:
                logging.warning(f'Collection {item.get("acronym")} not found.')
                continue

            logging.info(item)
            cls.create_or_update(
                user=user,
                collection=collection,
                directory_name=item.get('directory_name'),
                path=item.get('path'),
                active=item.get('active', True),
            )

    @classmethod
    def create_or_update(
        cls,
        user,
        collection,
        directory_name,
        path,
        active,
    ):
        try:
            obj = cls.objects.get(collection=collection, path=path)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = timezone.now()
            obj.collection = collection
        
        obj.updated_by = user
        obj.updated = timezone.now()
        obj.directory_name = directory_name
        obj.path = path
        obj.active = active
     
        obj.save()
        logging.info(f'{collection.acron3} - {directory_name} - {path}')
        return obj

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['collection', 'path'], name='unique_collection_path')
        ]


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
    def get_number_of_expected_files_by_day(cls, collection, date):
        files_by_day = cls.objects.filter(
            models.Q(collection__acron3=collection) &
            models.Q(start_date__lte=date) &
            (models.Q(end_date__gte=date) | models.Q(end_date__isnull=True))
        )

        if files_by_day.count() > 1:
            raise MultipleFilesPerDayForTheSameDateError(_("ERROR. Please, set the field end_date for the collection {collection}."))

        if files_by_day.count() == 0:
            raise UndefinedCollectionFilesPerDayError(_("ERROR. Please, set the number of files per day for the collection {collection}."))
        
        return int(files_by_day.get().quantity)

    @classmethod
    def load(cls, data, user):
        for item in data:
            try:
                collection = Collection.objects.get(acron3=item.get('acronym'))
            except Collection.DoesNotExist:
                logging.warning(f'Collection {item.get("acronym")} not found.')
                continue

            logging.info(item)
            cls.create_or_update(
                user=user,
                collection=collection,
                start_date=item.get('start_date'),
                quantity=item.get('quantity'),
                end_date=item.get('end_date'),
            )

    @classmethod
    def create_or_update(
        cls,
        user,
        collection,
        start_date,
        quantity,
        end_date,
    ):
        try:
            obj = cls.objects.get(collection=collection, start_date=start_date)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = timezone.now()
            obj.collection = collection

        obj.updated_by = user
        obj.updated = timezone.now()
        obj.start_date = start_date
        obj.quantity = quantity
        obj.end_date = end_date
        
        obj.save()
        logging.info(f'{collection.acron3} - {start_date} - {quantity}')
        return obj

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['collection', 'start_date'], name='unique_collection_start_date')
        ]


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
    
    @classmethod
    def load(cls, data, user):
        for item in data:
            try:
                collection = Collection.objects.get(acron3=item.get('acronym'))
            except Collection.DoesNotExist:
                logging.warning(f'Collection {item.get("acronym")} not found.')
                continue

            logging.info(item)
            cls.create_or_update(
                user=user,
                collection=collection,
                email=item.get('e-mail'),
                name=item.get('name'),
                position=item.get('position'),
                active=item.get('active', True),
            )

    @classmethod
    def create_or_update(
        cls,
        user,
        collection,
        email,
        name,
        position,
        active,
    ):
        try:
            obj = cls.objects.get(collection=collection, email=email)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = timezone.now()
            obj.collection = collection
            obj.email = email

        obj.updated_by = user
        obj.updated = timezone.now()        
        obj.name = name
        obj.position = position
        obj.active = active
        
        obj.save()
        logging.info(f'{collection.acron3} - {name} - {position} - {email}')
        return obj
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['collection', 'email'], name='unique_collection_email')
        ]


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
