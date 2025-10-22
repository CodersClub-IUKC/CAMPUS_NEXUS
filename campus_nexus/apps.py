from django.apps import AppConfig


class CampusNexusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'campus_nexus'

    def ready(self):
        from . import signals  # noqa