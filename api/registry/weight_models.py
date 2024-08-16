from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class WeightConfiguration(models.Model):
    version = models.CharField(max_length=50, unique=True)
    threshold = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1000)], default=20.0
    )
    active = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["active"],
                condition=models.Q(active=True),
                name="unique_active_weight_configuration",
            )
        ]

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

    class Meta:
        ordering = ["provider"]
        unique_together = ["weight_configuration", "provider"]

    def __str__(self):
        return f"{self.provider} - {self.weight}"

    @classmethod
    def get_active_weights(cls):
        try:
            active_config = WeightConfiguration.objects.filter(active=True).get()
        except ObjectDoesNotExist:
            return {}, 0.0
        except Exception as e:
            raise Exception(f"Failed to load settings: {str(e)}")

        weight_items = cls.objects.filter(weight_configuration=active_config)

        weights = {item.provider: item.weight for item in weight_items}
        threshold = active_config.threshold

        return weights, threshold
