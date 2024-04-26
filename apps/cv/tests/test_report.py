# IDE: PyCharm
# Project: cv
# Path: ${DIR_PATH}
# File: ${FILE_NAME}
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-10-29 (y-m-d) 5:37 PM
import pathlib

# from django.test import TestCase, SimpleTestCase, TransactionTestCase
from unittest import TestCase

from django.conf import settings

from .. import models
from ..reports import standard_report as report


class TestCompletePDFReport(TestCase):

    def setUp(self) -> None:
        self.profiles = [*models.CVUserProfile.objects.all()[:5]]
        assert self.profiles, 'Has no profiles to testing'

    def test_report(self):
        settings.DEBUG = True
        for profile in self.profiles:
            filename = str(pathlib.Path(__file__).parent / f'media/{self.__class__.__name__}-{profile.user.username}-{profile.user.pk}.pdf')
            self.report = report.CompletePDFReport(profile, filename=filename, debug=False)
            self.report.report()
