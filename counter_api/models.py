import hashlib
import secrets

from django.db import models
from django.utils import timezone


class APIKey(models.Model):
    name = models.CharField(max_length=120)
    digest = models.CharField(max_length=64, unique=True, editable=False)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, name, expires_at=None):
        value = secrets.token_urlsafe(32)
        digest = hashlib.sha256(value.encode()).hexdigest()
        key = cls.objects.create(
            name=name,
            digest=digest,
            expires_at=expires_at,
        )

        return key, value

    @classmethod
    def authenticate(cls, value):
        if not value:
            return None

        digest = hashlib.sha256(value.encode()).hexdigest()
        key = cls.objects.filter(digest=digest, active=True).first()
        if not key:
            return None

        if key.expires_at and key.expires_at <= timezone.now():
            return None

        cls.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key

    def __str__(self):
        return self.name
