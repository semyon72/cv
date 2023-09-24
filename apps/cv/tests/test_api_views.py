# IDE: PyCharm
# Project: cv
# Path: apps/cv/tests
# File: test_api_views.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-07-03 (y-m-d) 9:58 AM

import datetime
import functools
import pathlib
from urllib.parse import urlparse
import base64
from hashlib import md5
from typing import Type

from django.conf import settings
from django.test.utils import override_settings
from django.contrib.auth.models import User
from django.core.files import File
from django.db.models import Model
from django.forms import model_to_dict
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import MULTIPART_CONTENT, encode_multipart, BOUNDARY, Client
from django.utils.encoding import force_bytes
from django.views.static import serve as static_serve
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient, APITestCase

from apps.cv import models, views, serializers


class TestUserRetrieveUpdate(TestCase):

    def setUp(self) -> None:
        self.user_model: User = get_user_model()
        self.user = self.user_model.objects.create_user(username='test_user', password='12345678', email='test_user@cv.lan')

        self.url = reverse('cv:user')
        self.factory = APIRequestFactory()
        self.view = views.UserRetrieveUpdate.as_view()

    def test_01_common(self):
        self.assertIsNotNone(self.user.pk)

        # Success
        # login
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        # retrieve
        # should return [pk, username, email, firstname, lastname, date_joined]
        # only for current logged user
        response = self.view(request)
        tres = self.user._meta.model.objects.values(
            'id', 'username', 'email', 'first_name', 'last_name', 'date_joined',
        ).get(pk=self.user.pk)

        # fix to compare
        tres['profile'] = reverse('cv:profile', request=request)

        date_joined_field = self.view.view_class.serializer_class().fields['date_joined']
        date_joined = date_joined_field.to_internal_value(response.data['date_joined'])
        self.assertDictEqual(tres, response.data | {'date_joined': date_joined})

        # update
        # allow to modify [firstname, lastname]
        # should return [pk, username, email, firstname, lastname, date_joined]
        # only for current logged user
        upd_data = response.data | {'first_name': 'FIRST_NAME fgsfgsfd', 'last_name': 'LAST_NAME ;sdjlsdg'}
        request = self.factory.put(self.url, data=upd_data)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertDictEqual(upd_data, response.data)
        current_data = response.data

        # Unsuccessful

        # update
        upd_data = upd_data | {
            'username': 'USERNAME fgsfgsfd',
            'email': 'www@ttt.lan',
            'date_joined': date_joined_field.to_representation(datetime.datetime.now()),
        }
        request = self.factory.put(self.url, data=upd_data)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertDictEqual(current_data, response.data)

        # - current logged out user try
        # retrieve, update
        for faction in (self.factory.get, self.factory.put):
            with self.subTest(f'unauthenticated access, Action: {faction.__name__}'):
                request = faction(self.url, data=upd_data)
                response = self.view(request)
                self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class TestProfile(TestCase):

    def setUp(self) -> None:
        user_model: User = get_user_model()
        self.dummy_user = user_model.objects.create_user(
            username='dummy_test_user', password='12345678', email='dummy_test_user@cv.lan'
        )
        self.user = user_model.objects.create_user(username='test_user', password='12345678', email='test_user@cv.lan')
        self.profile = models.CVUserProfile.objects.create(user=self.user)

        self.url = reverse('cv:profile')
        self.factory = APIRequestFactory()
        self.view = views.Profile.as_view()

    def test_01_common(self):
        self.assertIsNotNone(self.user.pk)
        self.assertIsNotNone(self.profile.pk)

        # Success

        # login
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user)
        date_joined_field = self.view.view_class.serializer_class().fields['user'].fields['date_joined']

        with self.subTest(f'retrieve url {self.url}'):
            # retrieve
            # should return [profile.pk, [user.pk, username, email, firstname, lastname, date_joined, url], birthday, photo]
            # only for current logged user
            response = self.view(request)
            tres = {'id': 1,
                    'user': {'id': 2, 'username': 'test_user', 'email': 'test_user@cv.lan',
                             'first_name': '', 'last_name': '',
                             'date_joined': date_joined_field.to_representation(self.user.date_joined),
                             'url': reverse('cv:user', request=request),
                             },
                    'birthday': None, 'photo': None}
            self.assertDictEqual(tres, response.data)

        _url = reverse('cv:profile', [self.profile.pk])
        with self.subTest(f'retrieve url {_url}'):
            # retrieve with id
            client = APIClient()
            client.force_authenticate(user=self.user)
            response = client.get(_url)
            self.assertDictEqual(tres, response.data)

        with self.subTest(f'update url {self.url}'):
            # update
            # also try to change the writable fields in user - it ignores
            birthday_field = self.view.view_class.serializer_class().fields['birthday']
            upd_data = {'user': {'first_name': 'FIRST_NAME Will be ignored', 'last_name': 'LAST_NAME Will be ignored'},
                        'birthday': birthday_field.to_representation(datetime.date.fromisoformat('2001-12-04'))}
            request = self.factory.put(self.url, data=upd_data, format="json")
            force_authenticate(request, user=self.user)
            response = self.view(request)
            tres['birthday'] = upd_data['birthday']
            self.assertDictEqual(tres, response.data)

        current_data = response.data

        # Unsuccessful
        with self.subTest(f'unsuccessful update url {self.url}'):
            # update
            # try to change user and other read_only fields
            new_birthday = birthday_field.to_representation(datetime.date.fromisoformat('1991-01-01'))
            upd_data = {'user': {'id': self.dummy_user.pk, 'username': 'ttt_test_user', 'email': 'ttt_test_user@cv.lan'},
                        'birthday': new_birthday}
            request = self.factory.put(self.url, data=upd_data, format="json")
            force_authenticate(request, user=self.user)
            response = self.view(request)
            current_data['birthday'] = new_birthday
            # probably, better to test the database data
            self.assertDictEqual(current_data, response.data)

        # - current logged out user try
        # retrieve, update
        for faction, upd_data in ((self.factory.get, None), (self.factory.put, {'birthday': tres['birthday']})):
            with self.subTest(f'unauthenticated access, Action: {faction.__name__}'):
                request = faction(self.url, data=upd_data)
                response = self.view(request)
                self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_second_creation_is_denied(self):
        self.assertIsNotNone(self.profile)
        self.assertIsNotNone(self.profile.pk)

        birthday_field = self.view.view_class.serializer_class().fields['birthday']
        data = {
            'user': self.user.pk,
            'birthday': birthday_field.to_representation(datetime.date.fromisoformat('2010-10-10'))
        }
        request = self.factory.post(self.url, data=data, format="json")
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_delete(self):
        self.assertIsNotNone(self.profile)
        self.assertIsNotNone(self.profile.pk)

        request = self.factory.delete(self.url)
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_create(self):
        self.profile.delete()
        self.assertIsNone(self.profile.pk)
        self.assertEqual(0, len(self.profile._meta.model.objects.all()))

        birthday_field = self.view.view_class.serializer_class().fields['birthday']
        data = {
            'birthday': birthday_field.to_representation(datetime.date.fromisoformat('2010-10-10'))
        }
        request = self.factory.post(self.url, data=data, format="json")
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        profile = self.profile._meta.model.objects.get(pk=response.data['id'])
        self.assertEqual(self.user, profile.user)

    def _test_update_multipart_json(self, request):
        force_authenticate(request, user=self.user, token=None)

        self.assertIsNone(self.profile.photo.name)
        response = self.view(request)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.profile.refresh_from_db()
        dst_img_path = pathlib.Path(self.profile.photo.path)
        self.assertTrue(dst_img_path.exists() and dst_img_path.is_file())

        # factory, in this subtest, is used because APIClient (Client) together with
        # `from django.test.utils import override_settings` doesn't allow do the redefinition DEBUG into True
        # (at moment loading path-es) only for this test if we don't run this test separately.
        request = self.factory.get(response.data['photo'])
        resp_img_path = pathlib.Path(urlparse(response.data['photo']).path)
        response = static_serve(request, resp_img_path.name, document_root=settings.MEDIA_ROOT)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        dst_img_path.unlink(missing_ok=True)

    def test_update_multipart(self):
        src_img_path = pathlib.Path(settings.MEDIA_ROOT / 'boy-909552_960_720.jpg')
        content = encode_multipart(
            BOUNDARY,
            {
                'birthday': datetime.date(2000, 1, 10),
                'photo': File(open(src_img_path, 'rb'), name=src_img_path.name)
            },
        )

        request = self.factory.put(self.url, content, content_type=MULTIPART_CONTENT)
        self._test_update_multipart_json(request)

    def test_update_json(self):
        src_img_path = pathlib.Path(settings.MEDIA_ROOT / 'boy-909552_960_720.jpg')

        content = {
            'birthday': datetime.date(2002, 2, 20),
            'photo': base64.b64encode(open(src_img_path, 'rb').read()).decode()
        }
        request = self.factory.put(self.url, content, format='json')
        self.assertEqual('application/json', request.content_type)
        self._test_update_multipart_json(request)


class TestProfilePhotoUpdate(APITestCase):

    def setUp(self) -> None:
        self.profile_photo_view_name = 'cv:profile-photo'
        self.password = '12345678'
        self.src_img_path = pathlib.Path(settings.MEDIA_ROOT / 'boy-909552_960_720.jpg')

    @functools.cached_property
    def users(self) -> list[User]:
        user_model: User = get_user_model()
        return [
            user_model.objects.create_user(
                username='test_user', password=self.password, email='test_user@cv.lan'
            ),
            user_model.objects.create_user(
                username='bad_test_user', password=self.password, email='bad_test_user@cv.lan'
            ),
        ]

    @functools.cached_property
    def profile(self) -> models.CVUserProfile:
        return models.CVUserProfile.objects.create(
            user=self.users[0],
            birthday=datetime.date(2001, 1, 10),
        )

    def _test_changes_in_databse(self, response: Response):
        # 1 test response is Ok
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # 2 test the changes in database
        self.assertIsNone(self.profile.photo.name)

        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.photo.name, self.src_img_path.name)

        # 3 test the file created, indeed
        res_img_path = pathlib.Path(self.profile.photo.path)
        self.assertTrue(res_img_path.exists() and res_img_path.is_file())

        # 4 test that files is binary equal
        with self.src_img_path.open('rb') as src_f:
            with res_img_path.open('rb') as res_f:
                self.assertEqual(md5(src_f.read()).hexdigest(), md5(res_f.read()).hexdigest())

        res_img_path.unlink(missing_ok=True)

    def _reset_profile_photo(self):
        self.profile  # has the side effect - it creates an instance of the profile and caches it
        if self.profile.photo.name is not None:
            self.profile.photo = None
            self.profile.save()

    def test_multipart_update(self):
        self._reset_profile_photo()

        # run request
        client = APIClient()
        client.login(username=self.profile.user.username, password=self.password)

        content = encode_multipart(
            BOUNDARY,
            {'photo': File(open(self.src_img_path, 'rb'), name=self.src_img_path.name)},
        )
        response = client.put(reverse(self.profile_photo_view_name), content, content_type=MULTIPART_CONTENT)

        self._test_changes_in_databse(response)

    def test_json_base64_update(self):
        self._reset_profile_photo()

        # run request
        client = APIClient()
        client.login(username=self.profile.user.username, password=self.password)

        content = {'photo': base64.b64encode(open(self.src_img_path, 'rb').read()).decode()}
        response = client.put(reverse(self.profile_photo_view_name), content, format='json')

        self._test_changes_in_databse(response)

    def test_file_upload_update(self):
        self._reset_profile_photo()

        # run request
        client = APIClient()
        client.login(username=self.profile.user.username, password=self.password)

        # Content-Disposition: attachment; name="photo"; filename="coffee.png"
        # Content-Type: image/ipg
        with open(self.src_img_path, 'rb') as f:
            content = f.read()
        response = client.put(
            reverse(self.profile_photo_view_name),
            content,
            content_type='image/ipg',
            # name="photo"; has no sense to put in the header because FileUploadParser ignores it
            HTTP_CONTENT_DISPOSITION=f'attachment; filename="{self.src_img_path.name}"'
        )

        self._test_changes_in_databse(response)

    def _test_method_not_allowed(self, method_name):
        client = APIClient()
        client.login(username=self.profile.user.username, password=self.password)
        method = getattr(client, method_name, None)
        if method is None:
            raise ValueError(f'APIClient has no method `{method_name}`')
        response = method(reverse(self.profile_photo_view_name))
        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, response.status_code)

    def test_create_is_not_allowed(self):
        self._test_method_not_allowed('delete')

    def test_delete_is_not_allowed(self):
        self._test_method_not_allowed('post')

    def test_get_is_not_allowed(self):
        self._test_method_not_allowed('get')


class TestResource(TestCase):

    def setUp(self) -> None:
        user_model: User = get_user_model()
        self.user = user_model.objects.create_user(
            username='test_user', password='12345678', email='test_user@cv.lan'
        )

        self.staff_user = user_model.objects.create_user(
            username='staff_user', password='12345678', email='staff_user@cv.lan', is_staff=True
        )
        self.url_lc = reverse('cv:resource-lc')
        self.factory = APIRequestFactory()
        self.view_lc = views.ResourcesListCreate.as_view()
        self.view_rud = views.ResourcesRetrieveUpdateDestroy.as_view()

        self.test_resources = ('skype', 'site', 'linkedin', 'telegram')

    def test_01_create(self):
        # only staff can create
        for i, res in enumerate(self.test_resources, start=1):
            with self.subTest(f'resource {i}: `{res}`'):
                data = {'resource': res}
                request = self.factory.post(self.url_lc, data=data)
                force_authenticate(request, user=self.staff_user)
                response = self.view_lc(request)
                self.assertDictEqual(data | {'id': i}, response.data)
                self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        all_res = list(views.ResourcesListCreate.serializer_class.Meta.model.objects.values().all())
        self.assertEqual(len(self.test_resources), len(all_res))

        # fail creation for duplicate
        res = self.test_resources[0]
        with self.subTest(f'resource 1 (duplicate is denied): `{res}`'):
            request = self.factory.post(self.url_lc, data={'resource': res})
            force_authenticate(request, user=self.staff_user)
            response = self.view_lc(request)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # fail creation for plain user
        res = 'ddddd'
        with self.subTest(f'resource 1 (plain user is forbidden): `{res}`'):
            request = self.factory.post(self.url_lc, data={'resource': res})
            force_authenticate(request, user=self.user)
            response = self.view_lc(request)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # anyone can retrieve (at least registered users)
        # successful list for plain user
        with self.subTest('list resource for plain user'):
            request = self.factory.get(self.url_lc)
            force_authenticate(request, user=self.user)
            response = self.view_lc(request)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertListEqual(all_res, response.data)

    def test_02_retrieve(self):
        # any can retrieve
        model: Model = self.view_rud.view_class.serializer_class.Meta.model
        res_objs = [model.objects.create(resource=res_val) for res_val in self.test_resources]
        test_obj = res_objs[2]
        self.url_rud = reverse('cv:resource-rud', [test_obj.pk])
        with self.subTest(f'resource {test_obj.pk}: `{test_obj.resource}`'):
            request = self.factory.get(self.url_rud)
            response = self.view_rud(request, pk=test_obj.pk)
            self.assertDictEqual(model_to_dict(test_obj), response.data)
            self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_03_update(self):
        # only staff can update
        model: Model = self.view_rud.view_class.serializer_class.Meta.model
        test_obj = model.objects.create(resource=self.test_resources[1])

        client = APIClient()

        for user, resource, status_code, msg in (
                (self.user, 'user', status.HTTP_403_FORBIDDEN, 'forbidden'),
                (self.staff_user, 'staff', status.HTTP_200_OK, 'successful'),
                (None, 'None', status.HTTP_403_FORBIDDEN, 'forbidden')
        ):
            client.force_authenticate(user=user, token=None)
            data = {'resource': resource}
            with self.subTest(f"resource updated {msg} {test_obj.pk}: `{data['resource']}`"):
                response = client.put(reverse('cv:resource-rud', [test_obj.pk]), data, format='json')
                self.assertEqual(status_code, response.status_code)
                if status_code == status.HTTP_200_OK:
                    self.assertDictEqual(model_to_dict(test_obj) | data, response.data)
                    test_obj.refresh_from_db()
                else:
                    self.assertDictEqual(model_to_dict(test_obj), model_to_dict(model.objects.get(pk=test_obj.pk)))

    def test_04_delete(self):
        # only staff can delete
        model: Model = self.view_rud.view_class.serializer_class.Meta.model
        test_obj = model.objects.create(resource=self.test_resources[1])

        client = APIClient()

        for user, resource, status_code, msg in (
                (self.user, 'user', status.HTTP_403_FORBIDDEN, 'forbidden for `user`'),
                (self.staff_user, 'staff', status.HTTP_204_NO_CONTENT, 'successful for `staff`'),
                (None, 'None', status.HTTP_403_FORBIDDEN, 'forbidden for `anonymous`')
        ):
            client.force_authenticate(user=user, token=None)
            with self.subTest(f"delete resource `{test_obj.pk}`: {msg}"):
                response = client.delete(reverse('cv:resource-rud', [test_obj.pk]))
                self.assertEqual(status_code, response.status_code)
                if status_code == status.HTTP_204_NO_CONTENT:
                    test_obj.pk = None
                    test_obj.save()
                else:
                    self.assertDictEqual(model_to_dict(test_obj), model_to_dict(model.objects.get(pk=test_obj.pk)))


class TestTechnology(TestCase):

    def setUp(self) -> None:
        user_model: User = get_user_model()
        self.user = user_model.objects.create_user(
            username='test_user', password='12345678', email='test_user@cv.lan'
        )
        self.staff_user = user_model.objects.create_user(
            username='staff_user', password='12345678', email='staff_user@cv.lan', is_staff=True
        )
        self.test_technologies = ('Python', 'SQL', 'Oracle')
        self.client = APIClient()

    def test_01_create(self):
        # only staff can create
        self.client.force_authenticate(user=self.staff_user, token=None)
        url = reverse('cv:technology-lc')
        for i, res in enumerate(self.test_technologies, start=1):
            with self.subTest(f'technology {i}: `{res}`'):
                data = {'technology': res}
                response = self.client.post(url, data=data)
                self.assertDictEqual(data | {'id': i}, response.data)
                self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        all_res = list(models.CVTechnologies.objects.values().all())
        self.assertEqual(len(self.test_technologies), len(all_res))

        # fail creation for duplicate
        tech = self.test_technologies[0]
        with self.subTest(f'technology 1 (duplicate is denied): `{tech}`'):
            response = self.client.post(url, data={'technology': tech})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # fail creation for plain user
        self.client.force_authenticate(self.user, token=None)
        tech = 'ddddd'
        with self.subTest(f'technology 1 (plain user is forbidden): `{tech}`'):
            response = self.client.post(url, data={'technology': tech})
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # anyone can retrieve (at least registered users)
        # successful list for plain user
        with self.subTest('list technology for plain user'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertListEqual(all_res, response.data)

    def test_02_retrieve(self):
        # any can retrieve
        self.client.force_authenticate(None, None)
        tech_objs = [models.CVTechnologies.objects.create(technology=tech_val) for tech_val in self.test_technologies]
        test_obj = tech_objs[2]
        url = reverse('cv:technology-rud', [test_obj.pk])
        with self.subTest(f'technology {test_obj.pk}: `{test_obj.technology}`'):
            response = self.client.get(url)
            self.assertDictEqual(model_to_dict(test_obj), response.data)
            self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_03_update(self):
        # only staff can update
        model: Type[Model] = models.CVTechnologies
        test_obj = model.objects.create(technology=self.test_technologies[1])
        url = reverse('cv:technology-rud', [test_obj.pk])

        for user, technology, status_code, msg in (
                (self.user, 'user', status.HTTP_403_FORBIDDEN, 'forbidden'),
                (self.staff_user, 'staff', status.HTTP_200_OK, 'successful'),
                (None, 'None', status.HTTP_403_FORBIDDEN, 'forbidden')
        ):
            self.client.force_authenticate(user=user, token=None)
            data = {'technology': technology}
            with self.subTest(f"update technology `{test_obj.pk}`:`{data['technology']}` is {msg}"):
                response = self.client.put(url, data, format='json')
                self.assertEqual(status_code, response.status_code)
                if status_code == status.HTTP_200_OK:
                    self.assertDictEqual(model_to_dict(test_obj) | data, response.data)
                    test_obj.refresh_from_db()
                else:
                    self.assertDictEqual(model_to_dict(test_obj), model_to_dict(model.objects.get(pk=test_obj.pk)))

    def test_04_delete(self):
        # only staff can delete
        model: Type[Model] = models.CVTechnologies
        test_obj = model.objects.create(technology=self.test_technologies[1])
        url = reverse('cv:technology-rud', [test_obj.pk])

        for user, technology, status_code, msg in (
                (self.user, 'user', status.HTTP_403_FORBIDDEN, 'forbidden for `user`'),
                (self.staff_user, 'staff', status.HTTP_204_NO_CONTENT, 'successful for `staff`'),
                (None, 'None', status.HTTP_403_FORBIDDEN, 'forbidden for `anonymous`')
        ):
            self.client.force_authenticate(user=user, token=None)
            with self.subTest(f"delete resource `{test_obj.pk}`: {msg}"):
                response = self.client.delete(url)
                self.assertEqual(status_code, response.status_code)
                if status_code == status.HTTP_204_NO_CONTENT:
                    test_obj.pk = None
                    test_obj.save()
                else:
                    self.assertDictEqual(model_to_dict(test_obj), model_to_dict(model.objects.get(pk=test_obj.pk)))


class TestEducation(TestCase):
    """
    CVEducation
        profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
        begin = models.DateField(default=datetime.date.today)
        end = models.DateField(null=True, default=None, blank=True)
        institution = models.CharField(max_length=248)
        speciality = models.CharField(max_length=248)
        degree = models.CharField(max_length=24)
        complete = models.BooleanField(default=True)
    """

    def setUp(self) -> None:
        self.client = APIClient()

    @functools.cached_property
    def profiles(self):
        user_model: User = get_user_model()
        profile_model = models.CVUserProfile
        return [
            profile_model.objects.create(
                user=user_model.objects.create_user(
                    username='test_user', password='12345678', email='test_user@cv.lan'
                ),
                birthday=datetime.date(2001, 1, 1)
            ),
            profile_model.objects.create(
                user=user_model.objects.create_user(
                    username='test_user1', password='12345678', email='test_user1@cv.lan'
                ),
                birthday=datetime.date(2004, 4, 4)
            ),
        ]

    @functools.cached_property
    def profile(self):
        return self.profiles[0]

    def get_object_model(self) -> Type[Model]:
        return models.CVEducation

    def get_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'begin': datetime.date(2010, 3, 5),
            'end': datetime.date(2013, 7, 7),
            'institution': 'Some university',
            'speciality': 'MBA',
            'degree': 'Bachelor',
            'complete': True,
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'begin': datetime.date(2014, 4, 4),
            'end': datetime.date(2015, 5, 5),
            'institution': 'UPD: Some university',
            'speciality': 'UPD: MBA',
            'degree': 'Master',
            'complete': True,
        }

    def create_object(self):
        return self.get_object_model().objects.create(**self.get_model_kwargs())

    def model_kwargs_to_data(self, model_kwargs: dict):
        """
            Transform model's kwargs into data to as it supports SerializerBy
            By default it transform all Model's instances into their PK
            exclude - list of fields that must be excluded
        """
        return {k: (v.pk if isinstance(v, Model) else v) for k, v in model_kwargs.items()}

    def get_view_name(self):
        return 'cv:education'

    def _test_object_profile(self, obj: Model):
        self.assertEqual(self.profile, obj.profile)

    def _test_object_created(self, response: Response):
        objs = self.get_object_model().objects.all()
        self.assertEqual(1, len(objs))
        obj = objs[0]
        self._test_object_profile(obj)

        self.assertDictEqual(response.data.serializer.to_representation(obj), response.data)

    def test_create(self):
        self.client.force_authenticate(self.profile.user, None)

        data = self.model_kwargs_to_data(self.get_model_kwargs())
        response = self.client.post(reverse(self.get_view_name()), data=data)

        # object always is created but with authenticated user's profile
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        self._test_object_created(response)

    def test_create_bad_profile(self, ignore_profile=False):
        # authenticated with self.profiles[0] (self.profile) - by default
        # and try to pass another profile
        # Result - will have object for self.profile
        self.client.force_authenticate(self.profile.user, None)

        # to testing xxx_ignore_profile
        create_kwargs = self.get_model_kwargs()
        if ignore_profile:
            del create_kwargs['profile']
        else:
            create_kwargs['profile'] = self.profiles[1]
        data = self.model_kwargs_to_data(create_kwargs)
        response = self.client.post(reverse(self.get_view_name()), data=data)

        # object always is created but with authenticated user's profile
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        self._test_object_created(response)

    def test_create_ignore_profile(self):
        # authenticated with self.profiles[0] (self.profile) - by default
        # and remove profile from data to create
        # Result - will have object for self.profile
        self.test_create_bad_profile(ignore_profile=True)

    def test_create_bad_user(self):
        # authenticated with self.profiles[1]
        # and will have object for self.profiles[1]
        # to testing xxx_bad_user
        self.client.force_authenticate(self.profiles[1].user, None)

        data = self.model_kwargs_to_data(self.get_model_kwargs())
        response = self.client.post(reverse(self.get_view_name()), data=data)

        # object always is created but with authenticated user's profile
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        objs = self.get_object_model().objects.all()
        self.assertEqual(1, len(objs))
        obj = objs[0]
        self.assertEqual(self.profiles[1], obj.profile)
        self.assertDictEqual(response.data.serializer.to_representation(obj), response.data)

    def test_retrieve(self):
        # only owner can retrieve
        self.client.force_authenticate(self.profile.user, None)
        obj = self.create_object()
        response = self.client.get(reverse(self.get_view_name(), kwargs={'pk': obj.pk}))

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertDictEqual(response.data.serializer.to_representation(obj), response.data)

    def test_retrieve_bad_user(self):
        # only owner can retrieve
        self.client.force_authenticate(self.profiles[1].user, None)
        obj = self.create_object()
        response = self.client.get(reverse(self.get_view_name(), [obj.pk]))

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_list(self, auth_profile: models.CVUserProfile = None):
        if auth_profile is None:
            auth_profile = self.profile
        self.client.force_authenticate(auth_profile.user, None)

        obj = self.create_object()
        obj1 = self.get_object_model().objects.create(**self.get_update_model_kwargs())
        response = self.client.get(reverse(self.get_view_name()))

        if auth_profile != self.profile:
            self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        else:
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertListEqual(response.data.serializer.to_representation([obj, obj1]), response.data)

    def test_list_bad_user(self):
        self.test_list(auth_profile=self.profiles[1])

    def test_update(self, ignore_profile=False):
        self.client.force_authenticate(self.profile.user, None)

        obj = self.create_object()
        data = self.model_kwargs_to_data(model_to_dict(obj) | self.get_update_model_kwargs())

        if ignore_profile:
            data.pop('profile')

        response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        obj.refresh_from_db()
        self.assertDictEqual(
            self.model_kwargs_to_data(model_to_dict(obj)),
            self.model_kwargs_to_data(data | {'profile': self.profile})
        )

    def test_update_ignore_profile(self):
        self.test_update(ignore_profile=True)

    def test_update_bad_profile(self):
        self.client.force_authenticate(self.profile.user, None)

        obj = self.create_object()
        data = self.model_kwargs_to_data(
            model_to_dict(obj) | self.get_update_model_kwargs() | {'profile': self.profiles[1]}
        )
        response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)

        # profiled objects like Education, the modification of .profile will be ignored
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        # test the profile was not modified
        obj.refresh_from_db()
        self.assertEqual(self.profile, obj.profile)
        # test the other data were modified
        self.assertDictEqual(
            self.model_kwargs_to_data(model_to_dict(obj)),
            self.model_kwargs_to_data(data | {'profile': self.profile})
        )

    def test_update_bad_user(self):
        self.client.force_authenticate(self.profiles[1].user, None)

        obj = self.create_object()
        data = self.model_kwargs_to_data(model_to_dict(obj) | self.get_update_model_kwargs())
        response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_delete(self):
        obj = self.create_object()
        self.client.force_authenticate(user=self.profile.user, token=None)
        response = self.client.delete(reverse(self.get_view_name(), kwargs={'pk': obj.pk}))
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        with self.assertRaises(type(obj).DoesNotExist):
            obj.refresh_from_db()

    def test_delete_bad_user(self):
        obj = self.create_object()
        self.client.force_authenticate(user=self.profiles[1].user, token=None)
        response = self.client.delete(reverse(self.get_view_name(), kwargs={'pk': obj.pk}))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        obj.refresh_from_db()


class TestHobby(TestEducation):
    """
    CVHobby
        profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
        description = models.TextField(null=True, blank=True)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVHobby

    def get_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'description': 'Some Hobby\'s description',
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'description': 'UPD: Some Hobby\'s description',
        }

    def get_view_name(self):
        return 'cv:hobby'


class TestLanguage(TestEducation):
    """
    CVLanguage
        profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
        lang = models.CharField(max_length=24)
        level = models.CharField(max_length=24)
        notes = models.CharField(max_length=248)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVLanguage

    def get_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'lang': 'Some Language',
            'level': 'Some Intermediate',
            'notes': 'Some Language notes'
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'lang': 'UPD: Some Language',
            'level': 'UPD: Some Intermediate',
            'notes': 'UPD: Some Language notes'
        }

    def get_view_name(self):
        return 'cv:language'


class TestProject(TestEducation):
    """
    CVProject
        profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
        description = models.CharField(max_length=248)
        prerequisite = models.CharField(max_length=248)
        result = models.CharField(max_length=48)
        begin = models.DateField(default=datetime.date.today)
        end = models.DateField(null=True, default=None, blank=True)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVProject

    def get_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'description': 'Some description',
            'prerequisite': 'Some prerequisite',
            'result': 'Some result',
            'begin': datetime.date(2010, 5, 5),
            'end': datetime.date(2011, 1, 1),
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'description': 'UPD: Some description',
            'prerequisite': 'UPD: Some prerequisite',
            'result': 'UPD: Some result',
            'begin': datetime.date(2011, 2, 2),
            'end': datetime.date(2013, 1, 1),
        }

    def get_view_name(self):
        return 'cv:project'


class TestWorkplace(TestEducation):
    """
    CVWorkplace
        profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
        workplace = models.CharField(max_length=248)
        begin = models.DateField(default=datetime.date.today)
        end = models.DateField(null=True, default=None, blank=True)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVWorkplace

    def get_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'workplace': 'Some workplace',
            'begin': datetime.date(2010, 5, 5),
            'end': datetime.date(2011, 1, 1),
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'workplace': 'UPD: Some workplace',
            'begin': datetime.date(2011, 2, 2),
            'end': datetime.date(2013, 1, 1),
        }

    def get_view_name(self):
        return 'cv:workplace'


class TestUserResource(TestEducation):
    """
        Resources are associated with the user
        Each user can have 'GitHub', 'telephone' etc

        CVUserResource
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            resource = models.ForeignKey(CVResources, on_delete=models.CASCADE)
            link = models.CharField(max_length=248)
    """

    @functools.cached_property
    def resources(self) -> list[models.CVResources]:
        """
            resource = models.CharField(max_length=24, unique=True)
            with value like 'telephone', 'upwork', 'facebook', 'tiktok',
            'instagram', 'tweeter', 'GitHub', 'GitLab' ....
        """
        return [models.CVResources.objects.create(resource=rn) for rn in ('telephone', 'upwork', 'facebook')]

    def get_object_model(self) -> Type[Model]:
        return models.CVUserResource

    def get_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'resource': self.resources[0],
            'link': '+38055-555-55-55'
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'profile': self.profile,
            'resource': self.resources[1],
            'link': 'https://upwork.com/some_user_identifier'
        }

    def get_view_name(self):
        return 'cv:user-resource'


class TestProjectTechnology(TestEducation):
    """
        Technologies that were used (+duration and notes) in a certain project
        `duration` can be null just for parent who is null also. null - means infinity (current)

        CVProjectTechnology
            project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
            technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
            duration = models.DurationField(null=True, blank=True)
            notes = models.CharField(max_length=248)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVProjectTechnology

    def get_model_kwargs(self) -> dict:
        return {
            'project': models.CVProject.objects.create(
                profile=self.profile, description='Some description', prerequisite='Some prerequisite',
                result='Some result', begin=datetime.date(2010, 5, 5), end=datetime.date(2011, 1, 1)
            ),
            'technology': models.CVTechnologies.objects.create(technology='Python'),
            'duration': datetime.timedelta(days=123),  # must be in [project.begin..project.end]
            'notes': 'Some notes'
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'project': models.CVProject.objects.create(
                profile=self.profile, description='UPD: Some description', prerequisite='UPD: Some prerequisite',
                result='UPD: Some result', begin=datetime.date(2011, 2, 2), end=datetime.date(2013, 1, 1)
            ),
            'technology': models.CVTechnologies.objects.create(technology='SQL'),
            'duration': datetime.timedelta(days=123),  # must be in [project.begin..project.end]
            'notes': 'UPD: Some notes'
        }

    def get_view_name(self):
        return 'cv:project-technology'

    def get_bad_profile_attr_object(self) -> tuple[str, Model]:
        return 'project', models.CVProject.objects.create(
            profile=self.profiles[1], description='Bad PROF-1: description', prerequisite='Bad PROF-1: prerequisite',
            result='Bad PROF-1: result', begin=datetime.date(2015, 5, 5), end=datetime.date(2016, 6, 6)
        )

    def _test_object_created(self, response: Response):
        # redefine this we eliminate to need the ancestor's test_create(...) override
        attr_name, bad_obj = self.get_bad_profile_attr_object()

        objs = self.get_object_model().objects.select_related(attr_name).all()
        self.assertEqual(1, len(objs))
        obj = objs[0]
        self.assertEqual(self.profile, getattr(obj, attr_name).profile)
        self.assertDictEqual(response.data.serializer.to_representation(obj), response.data)

    def test_create_bad_profile(self):
        self.client.force_authenticate(self.profile.user, None)

        create_kwargs = self.get_model_kwargs()
        attr_name, bad_obj = self.get_bad_profile_attr_object()
        create_kwargs[attr_name] = bad_obj

        data = self.model_kwargs_to_data(create_kwargs)
        response = self.client.post(reverse(self.get_view_name()), data=data)

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_create_ignore_profile(self):
        # like a stub for ancestor (ProjectTechnology has no profile but project field is required)
        self.client.force_authenticate(self.profile.user, None)

        create_kwargs = self.get_model_kwargs()
        attr_name, bad_obj = self.get_bad_profile_attr_object()
        del create_kwargs[attr_name]

        data = self.model_kwargs_to_data(create_kwargs)
        response = self.client.post(reverse(self.get_view_name()), data=data)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_bad_user(self):
        self.client.force_authenticate(self.profiles[1].user, None)

        data = self.model_kwargs_to_data(self.get_model_kwargs())
        response = self.client.post(reverse(self.get_view_name()), data=data)

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_update(self, ignore_profile=False):
        self.client.force_authenticate(self.profile.user, None)

        obj = self.create_object()
        data = self.model_kwargs_to_data(model_to_dict(obj) | self.get_update_model_kwargs())
        response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        obj.refresh_from_db()
        self.assertDictEqual(
            self.model_kwargs_to_data(model_to_dict(obj)),
            self.model_kwargs_to_data(data)
        )

    def test_update_ignore_profile(self):
        self.client.force_authenticate(self.profile.user, None)

        obj = self.create_object()
        data = self.model_kwargs_to_data(model_to_dict(obj) | self.get_update_model_kwargs())
        attr_name, bad_obj = self.get_bad_profile_attr_object()
        del data[attr_name]

        response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_bad_profile(self):
        self.client.force_authenticate(self.profile.user, None)

        obj = self.create_object()
        data = self.model_kwargs_to_data(
            model_to_dict(obj) | self.get_update_model_kwargs() | dict([self.get_bad_profile_attr_object()])
        )
        response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class TestWorkplaceResponsibility(TestProjectTechnology):
    """
        CVWorkplaceResponsibility
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
            responsibility = models.TextField()
            role = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVWorkplaceResponsibility

    def get_model_kwargs(self) -> dict:
        return {
            'workplace': models.CVWorkplace.objects.create(
                profile=self.profile, workplace='Some workplace',
                begin=datetime.date(2010, 5, 5), end=datetime.date(2011, 1, 1)
            ),
            'responsibility': 'Some responsibility',
            'role': 'Some role',
            'begin': datetime.date(2010, 5, 5),
            'end': datetime.date(2011, 1, 1)
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'workplace': models.CVWorkplace.objects.create(
                profile=self.profile, workplace='UPD: Some workplace',
                begin=datetime.date(2011, 3, 3), end=datetime.date(2012, 2, 2)
            ),
            'responsibility': 'UPD: Some responsibility',
            'role': 'UPD: Some role',
            'begin': datetime.date(2011, 5, 5),
            'end': datetime.date(2012, 1, 11)
        }

    def get_view_name(self):
        return 'cv:workplace-responsibility'

    def get_bad_profile_attr_object(self) -> tuple[str, Model]:
        return 'workplace', models.CVWorkplace.objects.create(
            profile=self.profiles[1], workplace='Bad WRKPL: Some workplace',
            begin=datetime.date(2011, 3, 3), end=datetime.date(2012, 2, 2)
        )


class TestWorkplaceProject(TestEducation):
    """
        CVWorkplaceProject
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
            project = models.OneToOneField(CVProject, on_delete=models.CASCADE)
    """

    def get_object_model(self) -> Type[Model]:
        return models.CVWorkplaceProject

    @functools.cached_property
    def workplaces(self):
        return [
            models.CVWorkplace.objects.create(
                profile=self.profile, workplace='Some #1 workplace',
                begin=datetime.date(2010, 5, 5), end=datetime.date(2011, 1, 1)
            ),
            models.CVWorkplace.objects.create(
                profile=self.profile, workplace='Some #2 workplace',
                begin=datetime.date(2011, 3, 3), end=datetime.date(2012, 7, 7)
            )
        ]

    @functools.cached_property
    def projects(self):
        return [
            # for self.workplaces[0]
            models.CVProject.objects.create(
                profile=self.profile, description='Some project #1 description for  WRKPL#1',
                prerequisite='Some project #1 prerequisite for WRKPL#1', result='Some result #1 for WRKPL#1',
                begin=datetime.date(2010, 5, 5), end=datetime.date(2010, 7, 7)
            ),
            # for self.workplaces[1]
            models.CVProject.objects.create(
                profile=self.profile, description='Some project #1 description for WRKPL#2',
                prerequisite='Some project #1 prerequisite for WRKPL#2', result='Some result #1 for WRKPL#2',
                begin=datetime.date(2011, 3, 3), end=datetime.date(2011, 9, 9),
            ),
            # for self.workplaces[1]
            models.CVProject.objects.create(
                profile=self.profile, description='Some project #2 description for WRKPL#2',
                prerequisite='Some project #2 prerequisite for WRKPL#2', result='Some result #2 for WRKPL#2',
                begin=datetime.date(2011, 10, 10), end=datetime.date(2012, 2, 2),
            ),
        ]

    def get_model_kwargs(self) -> dict:
        return {
            'workplace': self.workplaces[0],
            'project': self.projects[0],
        }

    def get_update_model_kwargs(self) -> dict:
        return {
            'workplace': self.workplaces[1],
            'project': self.projects[1],
        }

    def get_view_name(self):
        return 'cv:workplace-project'

    def _test_object_profile(self, obj: Model):
        self.assertEqual(self.profile, obj.workplace.profile)
        self.assertEqual(self.profile, obj.project.profile)

    def get_bad_profile_attr_objects(self) -> dict:
        return {
            'workplace': models.CVWorkplace.objects.create(
                profile=self.profiles[1], workplace='BAD: Some workplace with self.profiles[1]',
                begin=datetime.date(2010, 5, 5), end=datetime.date(2011, 1, 1)
            ),
            'project': models.CVProject.objects.create(
                profile=self.profiles[1], description='BAD: Some project description with self.profiles[1]',
                prerequisite='BAD: Some project prerequisite with self.profiles[1]',
                result='BAD: Some result with self.profiles[1]',
                begin=datetime.date(2011, 10, 10), end=datetime.date(2012, 2, 2),
            ),
        }

    def test_create_ignore_profile(self):
        """
            This test is like stub
        """
        self.client.force_authenticate(self.profile.user, None)

        for attr_name, bad_obj in self.get_bad_profile_attr_objects().items():
            with self.subTest(f'ignore {attr_name}'):
                create_kwargs = self.get_model_kwargs()
                del create_kwargs[attr_name]

                data = self.model_kwargs_to_data(create_kwargs)
                response = self.client.post(reverse(self.get_view_name()), data=data)

                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_bad_user(self):
        self.client.force_authenticate(self.profiles[1].user, None)

        data = self.model_kwargs_to_data(self.get_model_kwargs())
        response = self.client.post(reverse(self.get_view_name()), data=data)

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_update(self, ignore_profile=False):
        TestProjectTechnology.test_update(self, ignore_profile)

    def test_update_ignore_profile(self):
        # like a stub
        self.client.force_authenticate(self.profile.user, None)
        obj = self.create_object()
        for attr_name, bad_obj in self.get_bad_profile_attr_objects().items():
            with self.subTest(f'ignore {attr_name}'):
                data = self.model_kwargs_to_data(model_to_dict(obj) | self.get_update_model_kwargs())
                del data[attr_name]

                response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_bad_profile(self):
        self.client.force_authenticate(self.profile.user, None)
        obj = self.create_object()
        for attr_name, bad_obj in self.get_bad_profile_attr_objects().items():
            with self.subTest(f'bad {attr_name}'):
                data = self.model_kwargs_to_data(
                    model_to_dict(obj) | self.get_update_model_kwargs() | {attr_name: bad_obj}
                )
                response = self.client.put(reverse(self.get_view_name(), kwargs={'pk': obj.pk}), data=data)

                self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
