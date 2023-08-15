from account.models import EthAddressField
from django.db import models

# WHEN a Trusta Labs API call is made for verification,
# THEN the result of the call, including timestamps, passport addresses, and Trusta Labs scores, should be logged in a dedicated table, separate from the credential issuance.


class TrustaLabsScore(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    sybil_risk_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
