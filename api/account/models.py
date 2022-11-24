from django.db import models
from django.conf import settings

# Create your models here.

class Account(models.Model):
    address = models.CharField(max_length=100, blank=False, null=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        default=None
    )

class ApiKey(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    name = models.CharField(max_length=100, blank=False, null=False)
    client_id = models.CharField(max_length=100, blank=False, null=False)
    secret = models.CharField(max_length=100, blank=False, null=False)
