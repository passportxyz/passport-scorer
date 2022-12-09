from django.db import models
from django.conf import settings
from rest_framework_api_key.models import AbstractAPIKey
from scorer_weighted.models import Scorer

# Create your models here.


class Account(models.Model):
    address = models.CharField(max_length=100, blank=False, null=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account"
    )

    def __str__(self):
        return f"{self.address} - {self.user}"


class AccountAPIKey(AbstractAPIKey):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="api_key", default=None
    )


class Community(models.Model):
    class Meta:
        verbose_name_plural = "Communities"

    name = models.CharField(max_length=100, blank=False, null=False)
    description = models.CharField(
        max_length=100, blank=False, null=False, default="My community"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="community", default=None
    )
    scorer = models.ForeignKey(Scorer, on_delete=models.PROTECT, default=None)
