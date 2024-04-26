# IDE: PyCharm
# Project: cv
# Path: apps/cv/management/commands
# File: createuser.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-09-28 (y-m-d) 7:34 PM

import argparse

from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Adds user and his empty profile, if does not exist"

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("username", type=str)
        # getpass
        # https://stackoverflow.com/a/28610617
        # https://gist.github.com/namnv609/f462c194e80ed4048cd2
        parser.add_argument("password", type=str)
        parser.add_argument("email", type=str)

    def handle(self, *args, **parser_options):
        ...

