from django.apps import AppConfig


class ScorerWeightedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scorer_weighted"

    def ready(self):
        # Implicitly connect signal handlers decorated with @receiver.
        # from . import signals

        # Explicitly connect a signal handler.
        # pylint: disable=import-outside-toplevel
        # pylint: disable=import-outside-toplevel
        from registry.signals import registry_updated
        from scorer_weighted.computation import calculate_score

        # Explicitly connect a signal handler.
        registry_updated.connect(calculate_score)
