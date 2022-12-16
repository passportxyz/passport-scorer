import secrets

from django.conf import settings
from django.db import models
from rest_framework_api_key.models import AbstractAPIKey
from scorer_weighted.models import Scorer, WeightedScorer

from .deduplication import Rules


class EthAddressField(models.CharField):
    def get_prep_value(self, value):
        return str(value).lower()


class Nonce(models.Model):
    nonce = models.CharField(max_length=60, blank=False, null=False, unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    was_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.id} - {self.nonce}"

    def mark_as_used(self):
        self.was_used = True
        self.save()

    @classmethod
    def create_nonce(cls) -> str:
        nonce = Nonce(nonce=secrets.token_hex(30))
        nonce.save()
        return nonce.nonce


class Account(models.Model):
    address = EthAddressField(max_length=100, blank=False, null=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account"
    )

    def __str__(self):
        return f"{self.address} - {self.user}"


class AccountAPIKey(AbstractAPIKey):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="api_key", default=None
    )


def get_default_community_scorer():
    """Returns the default scorer that shall be used for communities"""
    ws = WeightedScorer()
    ws.save()
    return ws


class Community(models.Model):
    class Meta:
        verbose_name_plural = "Communities"

    name = models.CharField(max_length=100, blank=False, null=False)
    rules = models.CharField(
        max_length=100,
        blank=False,
        null=False,
        default=Rules.LIFO,
        choices=[(Rules.LIFO, "LIFO"), (Rules.FIFO, "FIFO")],
    )
    description = models.CharField(
        max_length=100, blank=False, null=False, default="My community"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="community", default=None
    )
    scorer = models.ForeignKey(
        Scorer, on_delete=models.PROTECT, default=get_default_community_scorer
    )

    def get_scorer(self) -> Scorer:
        if self.scorer.type == Scorer.Type.WEIGHTED:
            return self.scorer.weightedscorer
        elif self.scorer.type == Scorer.Type.WEIGHTED_BINARY:
            return self.scorer.binary_weighted_scorer
