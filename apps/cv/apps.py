from django.apps import AppConfig
from . import patches


class CvConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cv'

    def ready(self):
        patches.cv_patcher.connect()
