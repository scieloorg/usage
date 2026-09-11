from django.db import models
from django.utils.translation import gettext_lazy as _


class OpenSearchPartitionStrategy(models.TextChoices):
    ROLLOVER = "rollover", _("Continuous with size rollover")
    YEARLY = "yearly", _("One physical index per year")
