# IDE: PyCharm
# Project: cv
# Path: apps/cv/tests
# File: test_api_live_server.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-09-19 (y-m-d) 7:06 AM
import datetime
import functools
from typing import TextIO, Union, Optional

import requests

from bs4 import BeautifulSoup, Tag, SoupStrainer

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APILiveServerTestCase

from .. import models


class TestLoginViaRequests(APILiveServerTestCase):

    def setUp(self) -> None:
        self.user_kwargs = {
            'username': 'test_user',
            'email': 'test_user@cv.lan',
            'password': '12345678',
        }
        self.login_url = reverse('login')
        self.server_login_url = f"{self.live_server_url}{self.login_url}"

    @functools.cached_property
    def user(self) -> User:
        usr_model: User = get_user_model()
        user = usr_model.objects.create_user(**self.user_kwargs)
        return user

    def get_extract_login_form(self, content: Union[str, TextIO]) -> dict:
        soup = BeautifulSoup(content, 'lxml', parse_only=SoupStrainer('form'))
        login_form: Optional[Tag] = soup.find(action=self.login_url)
        # Parse fields
        form_dict = {}
        for fi in login_form.find_all('input'):
            name = fi.attrs.get('name')
            if name:
                form_dict[name] = fi.attrs.get('value')
        # return dict with data to request
        # like {username: , password: , csrf:}
        return form_dict

    def test_login(self):
        login_form_response = requests.get(self.server_login_url)
        self.assertEqual(status.HTTP_200_OK, login_form_response.status_code)

        login_data = self.get_extract_login_form(login_form_response.text)
        login_data |= {
            'username': self.user_kwargs['username'],
            'password': self.user_kwargs['password'],
            'next': reverse('cv:profile')
        }

        user = self.user  # has side effect - creates the user

        # new request must be based on cookie of previous response
        login_response = requests.post(self.server_login_url, login_data, cookies=login_form_response.cookies)
        # profile for this user does not exist yet
        self.assertEqual(status.HTTP_404_NOT_FOUND, login_response.status_code)

        # add profile
        models.CVUserProfile.objects.create(user=self.user, birthday=datetime.date(2001, 10, 11))
        # test again
        login_response = requests.post(self.server_login_url, login_data, cookies=login_form_response.cookies)
        self.assertEqual(status.HTTP_200_OK, login_response.status_code)

        # test response, json data
        test_resp_data = {
            'id': 1,
            'user': {
                'id': 1,
                'username': 'test_user',
                'email': 'test_user@cv.lan',
                'first_name': '',
                'last_name': '',
                # 'date_joined': '2023-09-19T15:28:17.030669Z',
                # 'url': 'http://localhost:52769/cv/api/user/'
            },
            'birthday': '2001-10-11',
            'photo': None
        }

        # exclude 'date_joined'. test_resp_data is fixed, but User.date_joined is auto generated data.
        # same issue for 'url'
        resp_data = login_response.json()
        resp_data['user'].pop('date_joined')
        user_url = resp_data['user'].pop('url')
        self.assertDictEqual(test_resp_data, resp_data)

        user_response = requests.get(user_url, cookies=login_response.history[0].cookies)
        # To skip the cookie complications should use requests Session
        self.assertEqual(status.HTTP_200_OK, login_response.status_code)

    def test_login_via_session(self):
        # initialize database
        # self.user has side effect - creates the user for first run
        models.CVUserProfile.objects.create(user=self.user, birthday=datetime.date(2001, 10, 11))

        s = requests.Session()
        # get login form
        login_form_response = s.get(self.server_login_url)
        self.assertEqual(status.HTTP_200_OK, login_form_response.status_code)

        # prepare POST login data
        login_data = self.get_extract_login_form(login_form_response.text)
        login_data |= {
            'username': self.user_kwargs['username'],
            'password': self.user_kwargs['password'],
            'next': reverse('cv:profile')
        }

        # login
        response = s.post(self.server_login_url, login_data)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # remove unnecessary cookie
        del s.cookies['csrftoken']

        # retrieve user's info from other url, to test the csrf works properly
        response = s.get(response.json()['user']['url'])
        self.assertEqual(status.HTTP_200_OK, response.status_code)
