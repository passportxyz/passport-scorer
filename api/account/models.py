from django.db import models
from django.conf import settings
from rest_framework_api_key.models import AbstractAPIKey

# Create your models here.

class Account(models.Model):
    address = models.CharField(max_length=100, blank=False, null=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        default=None
    )

class AccountAPIKey(AbstractAPIKey):
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="api_key",
        default=None
    )

class Communities(models.Model):
    name = models.CharField(max_length=100, blank=False, null=False)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="community",
        default=None
    )
