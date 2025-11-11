from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class StampMetadata(models.Model):
    """
    Global metadata for stamp providers.

    Phase 2 TODO: This will become the source of truth for stamp providers,
    with WeightConfigurationItem referencing this via ForeignKey.
    """

    provider = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="The provider name that matches the stamp provider field",
    )

    is_beta = models.BooleanField(
        default=False,
        help_text="Whether this stamp should display a beta badge in the UI",
    )

    class Meta:
        ordering = ["provider"]
        verbose_name = "Stamp Metadata"
        verbose_name_plural = "Stamp Metadata"

    def __str__(self):
        beta_indicator = " (BETA)" if self.is_beta else ""
        return f"{self.provider}{beta_indicator}"

    @classmethod
    def get_all_metadata_dict(cls):
        """
        Returns a dictionary of all stamp metadata keyed by provider.
        Useful for bulk fetching in API responses.
        """
        metadata = {}
        for item in cls.objects.all():
            metadata[item.provider] = {
                "isBeta": item.is_beta,
            }
        return metadata


class WeightConfiguration(models.Model):
    version = models.CharField(
        max_length=50,
        unique=True,
        help_text="Leave empty to generate version automatically",
        blank=True,
    )
    threshold = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1000)], default=20.0
    )
    active = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    csv_source = models.FileField(
        upload_to="weight_configurations/",
        null=True,
        blank=True,
        default=None,
        help_text="CSV file containing weight configuration",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["active"],
                condition=models.Q(active=True),
                name="unique_active_weight_configuration",
            )
        ]

    @classmethod
    def get_active_threshold(cls):
        try:
            active_config = cls.objects.filter(active=True).get()
        except Exception as e:
            raise Exception(f"Failed to load active threshold: {str(e)}")

        return active_config.threshold

    def __str__(self):
        return f"v:{self.version}"


class WeightConfigurationItem(models.Model):
    weight_configuration = models.ForeignKey(
        WeightConfiguration, on_delete=models.CASCADE, related_name="weights"
    )
    provider = models.CharField(max_length=100)
    weight = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(100)]
    )

    # Phase 1: Add nullable ForeignKey to StampMetadata
    # Phase 2 TODO: Make this non-nullable after data migration
    stamp_metadata = models.ForeignKey(
        StampMetadata,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="weight_configs",
        help_text="Link to stamp metadata (Phase 2: will become required)",
    )

    class Meta:
        ordering = ["provider"]
        unique_together = ["weight_configuration", "provider"]

    def __str__(self):
        return f"{self.provider} - {self.weight}"

    @classmethod
    def get_active_weights(cls):
        try:
            active_config = WeightConfiguration.objects.filter(active=True).get()
        except Exception as e:
            raise Exception(f"Failed to load active weights: {str(e)}")

        weight_items = cls.objects.filter(weight_configuration=active_config)

        weights = {item.provider: item.weight for item in weight_items}
        return weights
