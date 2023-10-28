# IDE: PyCharm
# Project: cv
# Path: apps/cv/tests
# File: test_serializers.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-07-18 (y-m-d) 9:06 AM
import datetime
import functools
import pathlib
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional, Any, Callable, Type, Union

from django.conf import settings
from django.contrib.auth.models import User, UserManager, AnonymousUser
from django.core.files import File
from django.core.files.storage import Storage
from django.db import IntegrityError
from django.db.models import QuerySet, Model
from django.db.transaction import atomic
from django.forms import model_to_dict
from django.test import TestCase
from django.test.client import encode_multipart, RequestFactory, MULTIPART_CONTENT, BOUNDARY
from rest_framework import parsers
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.fields import empty, CharField
from rest_framework.reverse import reverse
from rest_framework.request import Request as APIRequest
from rest_framework.serializers import Serializer

from apps.cv import models, serializers
from rest_framework.test import APITestCase, APIClient, APIRequestFactory, force_authenticate, ForceAuthClientHandler


def serialize_model_instance(instance: Model, field_callback: dict[str, Callable[[Model], Any]] = None) -> dict:
    """
        Alternative (simple) serialization model instance
    """
    if field_callback is None:
        field_callback = {}
    inst_dict = model_to_dict(instance)
    for field, callback in field_callback.items():
        inst_dict[field] = callback(instance)
    return inst_dict


class TestCRUBaseSerializerProto:
    serializer_class = None

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer
            For example:
            CVHobby
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                description = models.TextField(null=True, blank=True)

            TestBaseSerializer do this
        """
        self.factory = APIRequestFactory()

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        raise NotImplementedError

    def serialize_model_object(self, obj: Model, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        return serialize_model_instance(obj) | {**kwargs}

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        """
            It should return the data that needs to Serializer(data=kwargs)
            model_kwargs is the data returned self.get_model_kwargs()
            It was used in:
                test_create(...)
                test_update(...)
                test_update_xxx(...)

            mainly when the data for the Serializer should be generated
        """
        return model_kwargs.copy()

    def get_serializer_data(self) -> dict:
        """
            Returns data for Serializer(data=....)
            By default (self.get_model_kwargs()[1]
        """
        return self.model_kwargs_to_serializer_data(self.get_model_kwargs()[1])

    @functools.lru_cache
    def get_request(self, user=None, method='get', method_data: dict = None, **factory_kwargs):
        factory_method = getattr(self.factory, method)
        request = factory_method('/', data=method_data, **factory_kwargs)  # .get('/'), .post() or .put() doesn't matter
        # authenticate as profile.user
        if user is not None:
            request.user = user
        else:
            request.user = AnonymousUser()
        return request

    @functools.cached_property
    def serializer(self) -> serializers.CVBaseSerializer:
        return self.serializer_class()

    def get_filed_names_to_update(self) -> tuple:
        """
            Returns readonly Serializer fields by default.
            Used in:
                test_update(...)
                test_update_xxx(...)
            as parameter for self.update_data_for_serializer(...)
        """
        return tuple(fn for fn, f in self.serializer.fields.items() if f.read_only is not True)

    def get_serializer_update_data(self) -> dict:
        """
            It should be data that needs to Serializer(data=kwargs) on update test
            By default, it returns a copy of orig_data that has been updated by upd_data
            only for the fields passed as the field_names parameter.
            Used in:
                test_update(...)
                test_update_xxx(...)
        """
        orig_data = self.model_kwargs_to_serializer_data(self.get_model_kwargs()[0])
        upd_data = self.model_kwargs_to_serializer_data(self.get_model_kwargs()[1])
        field_names = self.get_filed_names_to_update()

        # get updated data as appropriate
        return orig_data | {fn: upd_data[fn] for fn in field_names if fn in upd_data}

    def create_object(self, **kwargs) -> Model:
        return self.serializer_class.Meta.model.objects.create(**self.get_model_kwargs()[0] | kwargs)


class TestCRUBaseSerializerMixin(TestCRUBaseSerializerProto):

    def post_test_retrieve(self, serializer: Serializer):
        pass

    def test_retrieve(self):
        ser = self.serializer
        ser.context['request'] = self.get_request()

        obj = self.create_object()
        ser.instance = obj
        self.assertDictEqual(ser.data, self.serialize_model_object(obj))
        self.post_test_retrieve(ser)

    def post_test_create(self):
        pass

    def test_create(self):
        ser = self.serializer
        ser.context['request'] = self.get_request()

        ser.initial_data = self.get_serializer_data()
        self.assertTrue(ser.is_valid())
        obj = ser.save()
        self.assertIsNotNone(obj.pk)
        self.assertDictEqual(ser.data, self.serialize_model_object(obj))
        self.post_test_create()

    def post_test_update(self):
        pass

    def test_update(self):
        ser = self.serializer
        ser.context['request'] = self.get_request()

        obj = self.create_object()
        ser.instance = obj
        orig_data = self.serialize_model_object(obj)  # just for debugging
        ser.initial_data = self.get_serializer_update_data()
        self.assertTrue(ser.is_valid())
        ser.save()
        # to make sure the data is serialized appropriately
        self.assertDictEqual(ser.data, self.serialize_model_object(obj))
        self.post_test_update()


class CVUserProfileMixin:

    profile_view_name = 'cv:profile'

    def get_profiles_kwargs(self) -> list[dict]:
        """
            CVUserProfile
                user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
                birthday = models.DateField(null=True, blank=True, default=None)
                photo = models.ImageField(null=True, blank=True)
        """

        user_kwargs = [
            {'username': 'test_dummy_user', 'email': 'test_dummy_user@cv_serializer.lan', 'password': '12345678'},
            {'username': 'test_user', 'email': 'test_user@cv_serializer.lan', 'password': '12345678'},
            {'username': 'test_some_user', 'email': 'test_some_user@cv_serializer.lan', 'password': '12345678'}
        ]
        return [{'user': args, 'birthday': None, 'photo': None} for args in user_kwargs]

    def get_profile_model(self) -> Type[models.CVUserProfile]:
        return models.CVUserProfile

    @functools.cached_property
    def profiles(self) -> list[models.CVUserProfile]:
        user_model = models.get_user_model()
        profile_model = self.get_profile_model()
        pkwargs = self.get_profiles_kwargs()
        return [profile_model.objects.create(user=user_model.objects.create_user(**pkw.pop('user'))) for pkw in pkwargs]


class TestRUBadUserMixin:

    def get_bad_user(self):
        raise NotImplementedError

    def test_retrieve_bad_user(self):
        # create object for self.profile
        obj = self.create_object()
        # but try to work as self.bad_user_profile
        self.serializer.context['request'] = self.get_request(self.get_bad_user())
        self.serializer.instance = obj
        with self.assertRaises(PermissionDenied) as exc:
            self.serializer.data
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)

    def test_update_bad_user(self):
        # create object for self.profile
        obj = self.create_object()

        # but try to work as self.bad_user_profile
        # defer the PermissionDenied on the save() stage
        self.serializer.context['request'] = self.get_request(self.get_bad_user())
        data = self.get_serializer_update_data()
        self.serializer.instance = obj
        self.serializer.initial_data = data
        self.assertTrue(self.serializer.is_valid())
        with self.assertRaises(PermissionDenied) as exc:
            self.serializer.save()
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)


class TestBaseSerializerCommonBehaviour(CVUserProfileMixin, TestCRUBaseSerializerProto, APITestCase):
    serializer_class = serializers.HobbySerializer

    @classmethod
    def setUpClass(cls):
        if not issubclass(cls.serializer_class, serializers.CVBaseSerializer):
            raise AssertionError(f'{cls.__name__}.serializer_class must be subclass serializers.CVBaseSerializer')
        super().setUpClass()

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': self.profile, 'description': 'Some description'},
        ]

    @functools.lru_cache
    def get_request(self, user=None, method='get', method_data: dict = None):
        if user is None:
            user = self.profile.user
        return super().get_request(user, method, method_data)

    @property
    def profile(self):
        return self.profiles[2]

    def get_bad_user(self):
        return self.profiles[0].user

    def test_request_required(self):
        ser = self.serializer

        with self.subTest('retrieve'):
            ser.instance = object()
            with self.assertRaises(AssertionError) as exc:
                ser.data
            self.assertEqual(self.serializer_class.assertion_messages['request_required'], str(exc.exception))

        # Because serializer_class = serializers.HobbySerializer
        # and CVHobby.description allows None
        with self.subTest('update'):
            ser.initial_data = {}
            self.assertTrue(ser.is_valid())
            with self.assertRaises(AssertionError) as exc:
                ser.save()
            self.assertEqual(self.serializer_class.assertion_messages['request_required'], str(exc.exception))

        with self.subTest('create'):
            # reset serializer
            del ser._validated_data
            ser.instance = None
            ser.initial_data = {}
            self.assertTrue(ser.is_valid())
            with self.assertRaises(AssertionError) as exc:
                ser.save()
            self.assertEqual(self.serializer_class.assertion_messages['request_required'], str(exc.exception))

    def test_instance_profile_required(self):

        ser = self.serializer

        ser.context['request'] = self.get_request()
        with self.subTest('retrieve'):
            ser.instance = object()
            with self.assertRaises(AssertionError) as exc:
                ser.data
            self.assertEqual(self.serializer_class.assertion_messages['profile_required'], str(exc.exception))

        with self.subTest('update'):
            ser.initial_data = {}
            self.assertTrue(ser.is_valid())
            with self.assertRaises(AssertionError) as exc:
                ser.save()
            self.assertEqual(self.serializer_class.assertion_messages['profile_required'], str(exc.exception))

        # 'create' has no sense to test
        # 'profile' should be automatically calculated from request.user and assigned

    def test_profile_autofilled_on_create(self):
        # dummy object - to check all pre-initialized properly
        obj = self.create_object()
        self.assertEqual(obj.profile, self.profile, 'Profiles are not same')

        # for full testing (if `profile` is declared and read-only)
        DummySerializer = type('DummySerializer', (self.serializer_class,), {})
        DummySerializer._declared_fields.pop('profile')

        ser = DummySerializer()

        request = self.get_request()
        ser.context['request'] = request
        # test, to ensure that self.get_request() works properly and get the self.profile.user by default
        self.assertEqual(self.profile.user, request.user, 'request.user and profile.user must be same')

        bad_profile = [p for p in self.profiles if self.get_bad_user() == p.user][0]
        self.assertNotEqual(bad_profile.user, request.user, 'request.user must be different from bad_profile.user')

        # the test itself
        description = 'some description'
        self.assertNotEqual(self.profile, bad_profile, 'profiles must be different')

        ser.initial_data = {'profile': bad_profile.pk, 'description': description}
        self.assertTrue(ser.is_valid())
        ser.save()
        self.assertEqual(ser.instance.profile, self.profile)
        self.assertGreater(ser.instance.pk, obj.pk)

    def test_check_owning(self):
        # create object for self.profile
        obj = self.create_object()
        # but try to work as self.bad_user_profile
        self.serializer.context['request'] = self.get_request(self.get_bad_user())
        with self.assertRaises(PermissionDenied) as exc:
            self.serializer.check_owning(obj)
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)


class TestBaseSerializer(TestRUBadUserMixin, CVUserProfileMixin, TestCRUBaseSerializerMixin, APITestCase):
    serializer_class = serializers.HobbySerializer

    @classmethod
    def setUpClass(cls):
        if not issubclass(cls.serializer_class, serializers.CVBaseSerializer):
            raise AssertionError(f'{cls.__name__}.serializer_class must be subclass serializers.CVBaseSerializer')
        super().setUpClass()

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': self.profile, 'description': 'Some description'},
            {'profile': self.profile, 'description': 'Updated some description'},
        ]

    def serialize_model_object(self, obj: Model, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        data = super().serialize_model_object(obj, **kwargs)
        return data | {
            'profile': reverse(self.profile_view_name, request=self.serializer.context.get('request', None))
        }

    @functools.lru_cache
    def get_request(self, user=None, method='get', method_data: dict = None):
        if user is None:
            user = self.profile.user
        return super().get_request(user, method, method_data)

    @functools.cached_property
    def profile(self):
        return self.profiles[2]

    def get_bad_user(self):
        return self.profiles[0].user

    def post_test_create(self):
        # test auto-filling of logged profile as profile field
        # this test allows to get rid of test_create_bad_user
        self.assertEqual(self.serializer.instance.profile, self.profile)

    def post_test_update(self):
        # to make sure the profile is the same
        self.assertEqual(self.serializer.instance.profile, self.profile)


class TestHobbySerializer(TestBaseSerializer):
    """
        It must be tested with a serializer that is subclass serializers.CVBaseSerializer

        CVHobby
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            description = models.TextField(null=True, blank=True)
    """
    serializer_class = serializers.HobbySerializer

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'profile': self.profile, 'description': 'Some description'},
            {'profile': self.profile, 'description': 'Updated some description'},
            {'profile': self.profile, 'description': None},
        ]


class TestLanguageSerializer(TestBaseSerializer):
    """
        It must be tested with a serializer that is subclass serializers.CVBaseSerializer

        CVLanguage
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            lang = models.CharField(max_length=24)
            level = models.CharField(max_length=24)
            notes = models.CharField(max_length=248)
    """
    serializer_class = serializers.LanguageSerializer

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'profile': self.profile, 'lang': 'English', 'level': 'Base', 'notes': 'Some notes'},
            {'profile': self.profile, 'lang': 'UPD: English', 'level': 'Intermediate', 'notes': 'UPD: Some notes'},
            {'profile': self.profile, 'lang': 'Ukraine', 'level': 'Native', 'notes': 'Some notes for Ukraine'},
        ]


class TestUserResourceSerializer(TestBaseSerializer):
    """
        It must be tested with a serializer that is subclass serializers.CVBaseSerializer

        CVUserResource
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            resource = models.ForeignKey(CVResources, on_delete=models.CASCADE)
            link = models.CharField(max_length=248)
    """
    serializer_class = serializers.UserResourceSerializer

    @functools.cached_property
    def resources(self) -> list[dict]:
        """
            Resources are like a dictionary that available for all users, such as:
            'email' - contact, default login email
            'skype', 'site', 'linkedin', 'telegram',
            'telephone', 'upwork', 'facebook', 'tiktok',
            'instagram', 'tweeter', 'GitHub', 'GitLab' ....

            resource = models.CharField(max_length=24, unique=True)
        """
        mngr = models.CVResources.objects
        return [
            {'resource': mngr.create(resource='email'), 'link': 'some_resource_mail@resource.lan'},
            {'resource': mngr.create(resource='skype'), 'link': 'live:.cid.f3a7ad7d8e959c3d'},
            {'resource': mngr.create(resource='site'), 'link': 'http://www.semyon72.lan'},
            {'resource': mngr.create(resource='linkedin'), 'link': 'https://ua.linkedin.com/in/some-person'},
            {'resource': mngr.create(resource='telegram'), 'link': '@semyon723'},
            {'resource': mngr.create(resource='telephone'), 'link': '+380675555555'}
        ]

    def get_model_kwargs(self) -> list[dict]:
        return [{'profile': self.profile, **res} for res in self.resources]

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        data = super().model_kwargs_to_serializer_data(model_kwargs)
        data['resource'] = data['resource'].pk
        return data

    def serialize_model_object(self, obj: Model, **kwargs):
        data = super().serialize_model_object(obj, **kwargs)
        data['resource'] = obj.resource.pk
        return data


class TestEducationSerializer(TestBaseSerializer):
    """
        It must be tested with a serializer that is subclass serializers.CVBaseSerializer

        CVEducation
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
            institution = models.CharField(max_length=248)
            speciality = models.CharField(max_length=248)
            degree = models.CharField(max_length=24)
            complete = models.BooleanField(default=True)
    """
    serializer_class = serializers.EducationSerializer

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': self.profile, 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 3, 1),
             'institution': 'Some university', 'speciality': 'Computer science', 'degree': 'Bachelor', 'complete': True},
            {'profile': self.profile, 'begin': datetime.date(2012, 3, 1), 'end': datetime.date(2012, 7, 12),
             'institution': 'Next university', 'speciality': 'Computer science', 'degree': 'Master', 'complete': True},
            {'profile': self.profile, 'begin': datetime.date(2010, 1, 1), 'end': None,
             'institution': 'Other university', 'speciality': 'Busyness', 'degree': 'Master', 'complete': True},
        ]

    def serialize_model_object(self, obj: Model, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        data = super().serialize_model_object(obj, **kwargs)
        data['begin'] = str(obj.begin)
        data['end'] = str(obj.end)
        return data

    # TODO: Probably need to add the date range crossing tests


class TestProjectSerializer(TestEducationSerializer):
    """
        It must be tested with a serializer that is subclass serializers.CVBaseSerializer

        CVProject
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            title = models.CharField(max_length=248)
            description = models.CharField(max_length=248)
            prerequisite = models.CharField(max_length=248)
            result = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
    """
    serializer_class = serializers.ProjectSerializer

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': self.profile, 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 3, 1),
             'title': 'Some project title', 'description': 'Some project description',
             'prerequisite': 'market requirements', 'result': 'is done'},
            {'profile': self.profile, 'begin': datetime.date(2012, 3, 1), 'end': datetime.date(2012, 7, 12),
             'title': 'Next project title', 'description': 'Next project description',
             'prerequisite': 'own needs', 'result': 'in process'},
            {'profile': self.profile, 'begin': datetime.date(2010, 1, 1), 'end': None,
             'title': 'Other project title', 'description': 'Other project description',
             'prerequisite': 'Busyness', 'result': 'investigation'},
        ]

    # TODO: Probably need to add the date range crossing tests


class TestWorkplaceSerializer(TestEducationSerializer):
    """
        It must be tested with a serializer that is subclass serializers.CVBaseSerializer

        CVWorkplace:
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            workplace = models.CharField(max_length=248)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
    """
    serializer_class = serializers.WorkplaceSerializer

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': self.profile, 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 3, 1),
             'workplace': 'Electrotyazghmash plant'},
            {'profile': self.profile, 'begin': datetime.date(2012, 3, 1), 'end': datetime.date(2012, 7, 12),
             'workplace': 'Kharkiv Customs'},
            {'profile': self.profile, 'begin': datetime.date(2010, 1, 1), 'end': None,
             'workplace': 'Freelancer'},
        ]

    # TODO: Probably need to add the date range crossing tests


class TestUserRetrieveUpdateSerializer(TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """
        django.contrib.auth.models.User
            fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
            read_only_fields = ['username', 'email', 'date_joined']
    """
    serializer_class = serializers.UserRetrieveUpdateSerializer

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'username': 'test_user', 'email': 'test_user@test.lan',
             'first_name': 'Test FN', 'last_name': 'Test_LN'},
            {'username': 'upd_test_user', 'email': 'upd_test_user@test.lan',
             'first_name': 'UPD: Test FN', 'last_name': 'UPD: Test LN'}
        ]

    def serialize_model_object(self, obj: Model, **kwargs):
        request = self.get_request(user=obj)
        dj_to_repr = self.serializer_class(context={'request': request})['date_joined'].to_representation

        fields_kwargs = {
            'id': obj.pk,
            'date_joined': dj_to_repr(obj.date_joined),
            'profile': reverse(self.serializer_class.view_name, request=request),
        }
        res = super().serialize_model_object(obj, **fields_kwargs)
        repr_fields = [*fields_kwargs, *self.get_model_kwargs()[0].keys()]
        return {k: v for k, v in res.items() if k in repr_fields}

    def create_object(self, **kwargs) -> Model:
        if not hasattr(self, '_current_object'):
            user_model: Type[User] = self.serializer_class.Meta.model
            self._current_object = user_model.objects.create_user(**self.get_model_kwargs()[0] | kwargs)

        return self._current_object

    def get_request(self, user=None, method='get', method_data: dict = None):
        if user is None:
            user = self.create_object()
        return super().get_request(user, method, method_data)

    def get_bad_user(self):
        if not hasattr(self, '_bad_user'):
            self._bad_user: User = self.serializer_class.Meta.model.objects.create_user(**self.get_model_kwargs()[1])

        return self._bad_user

    def test_create(self):
        with self.assertRaises(PermissionDenied):
            super().test_create()


class TestProfileSerializer(TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """
        CVUserProfile
            user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
                fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
                read_only_fields = ['username', 'email', 'date_joined']

            birthday = models.DateField(null=True, blank=True, default=None)
            photo = models.ImageField(null=True, blank=True)
    """
    serializer_class = serializers.ProfileSerializer

    def setUp(self) -> None:
        super().setUp()
        self.photo_file_path_orig = pathlib.Path(__file__).parent / 'media' / 'hedgehog-1215140_960_720.jpg'

    @functools.cached_property
    def users(self) -> list[User]:
        user_mgr: UserManager = self.serializer_class._declared_fields['user'].Meta.model.objects
        return [
            user_mgr.create_user(
                username='test_user', email='test_user@test.lan', first_name='Test FN', last_name='Test_LN'
            ),
            user_mgr.create_user(
                username='upd_test_user', email='upd_test_user@test.lan',
                first_name='UPD: Test FN', last_name='UPD: Test LN'
            )
        ]

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'user': self.users[0], 'birthday': datetime.date(2005, 5, 5)},
            {'user': self.users[1], 'birthday': datetime.date(1999, 9, 9)}
        ]

    def _get_test_representation_of_user(self, user: Model):
        # get a test representation of the user
        user_test_ser = TestUserRetrieveUpdateSerializer()
        user_test_ser.setUp()
        res = user_test_ser.serialize_model_object(user)
        res.pop('profile', None)
        user_test_ser.serializer.fields  # to initialize serializer.url_field_name
        res[user_test_ser.serializer.url_field_name] = reverse(
            'cv:user', request=user_test_ser.get_request(user=user)
        )
        return res

    def serialize_model_object(self, obj: Model, **kwargs):
        res = serialize_model_instance(
            obj, {
                'photo': lambda o: self.serializer_class(
                    context={'request': self.get_request()}
                ).fields['photo'].to_representation(o.photo),
                'birthday': lambda o: str(o.birthday) if o.birthday is not None else None,
            }
        ) | {'user': self._get_test_representation_of_user(obj.user)}

        return res

    def create_object(self, **kwargs) -> Model:
        if not hasattr(self, '_current_object'):
            profile_model: Type[models.CVUserProfile] = self.serializer_class.Meta.model
            self._current_object = profile_model.objects.create(**self.get_model_kwargs()[0] | kwargs)

        return self._current_object

    def get_request(self, user=None, method='get', method_data: dict = None):
        if user is None:
            user = self.users[0]
        request = APIRequest(
            super().get_request(user, method, method_data, content_type='application/json'),
            parsers=(parsers.JSONParser(), parsers.MultiPartParser(), parsers.FileUploadParser())
        )
        request.user = user

        return request

    def get_bad_user(self):
        if not hasattr(self, '_bad_user'):
            self._bad_user: User = self.get_model_kwargs()[1]['user']

        return self._bad_user

    def _get_photo_file_name(self, user: User, file_suffix='.jpg'):
        return '{}_{}{}'.format(user.username, user.pk, file_suffix)

    def test_create_with_image_file(self):
        storage: Storage = models.CVUserProfile._meta.get_field('photo').storage

        self.assertFalse(
            storage.exists(self.photo_file_path_orig.name),
            f'File `{self.photo_file_path_orig.name}` must not exist in {storage.location}'
        )

        # dummy request for authentication ...
        request = self.get_request()
        dst_file_name = self._get_photo_file_name(request.user)

        with File(open(self.photo_file_path_orig, 'rb'), name='m5eu6ueu.jpg') as f:
            ser = self.serializer_class(data={'photo': f}, context={'request': request})
            is_valid = ser.is_valid()
            self.assertTrue(is_valid)
            ser.save()

        try:
            obj = models.CVUserProfile.objects.get(user=request.user)
            # to make sure the data is serialized appropriately
            self.assertDictEqual(ser.data, self.serialize_model_object(obj))

            self.assertEqual(str(obj.photo), dst_file_name)
            # 3. file exists in destination
            self.assertTrue(storage.exists(dst_file_name))
        finally:
            # 4. unlink
            storage.delete(dst_file_name)


class TestProfilePhotoSerializer(TestProfileSerializer):
    """
        It allows to work only with `photo` field
        CVUserProfile
            user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
                fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
                read_only_fields = ['username', 'email', 'date_joined']

            birthday = models.DateField(null=True, blank=True, default=None)
            photo = models.ImageField(null=True, blank=True)
    """
    serializer_class = serializers.ProfilePhotoSerializer

    def setUp(self) -> None:
        super().setUp()
        self.photo1_file_path_orig = pathlib.Path(__file__).parent / 'media' / 'boy-909552_960_720.jpg'

    def test_create(self):
        with self.assertRaises(PermissionDenied) as exc:
            super().test_create()

    def _copy_photo_file_to_media(self, origin_file_path: pathlib.Path = None) ->pathlib.Path:
        origin_file_path = origin_file_path or self.photo_file_path_orig

        self.assertTrue(origin_file_path.is_file(), f'origin file does not exist {origin_file_path}')

        dst_file_path = settings.MEDIA_ROOT / origin_file_path.name
        shutil.copy(origin_file_path, dst_file_path, follow_symlinks=False)
        self.assertTrue(
            dst_file_path.is_file(), f'origin file `{origin_file_path}` is not copied to `{dst_file_path}`'
        )
        return dst_file_path

    def test_create_model_object(self):
        """
            This simple test shows that any filename can put as value of 'photo'
            Was left to the learning purposes to show subtleties of behaviour
        """

        photo_file_path = self._copy_photo_file_to_media()
        photo_field = self.serializer_class.Meta.model._meta.get_field('photo')
        origin_upload_to = photo_field.upload_to
        # turn `upload_to` off
        photo_field.upload_to = ''
        try:
            # File exists in target
            obj = self.serializer_class.Meta.model.objects.create(
                **self.get_model_kwargs()[0] | {'photo': photo_file_path.name}
            )

            self.assertEqual(str(obj.photo), photo_file_path.name)

            # Assign wrong filename (File does exist in target)
            wrong_photo_file_path = photo_file_path.with_stem(photo_file_path.name +'_wrong')
            self.assertFalse(wrong_photo_file_path.exists())
            obj.photo = wrong_photo_file_path.name
            obj.save()
            obj.refresh_from_db()
            self.assertEqual(str(obj.photo), wrong_photo_file_path.name)

            # create copy of file with different name due to name duplication
            self.assertTrue(photo_file_path.exists())
            with File(open(photo_file_path, 'rb'), name=photo_file_path.name) as f:
                obj.photo = f
                obj.save()
            try:
                self.assertNotEqual(str(obj.photo), photo_file_path.name)
                self.assertTrue(str(obj.photo).startswith(photo_file_path.stem))
            finally:
                # delete the file that was created
                pathlib.Path(obj.photo.path).unlink()
        finally:
            pathlib.Path(photo_file_path).unlink()
            photo_field.upload_to = origin_upload_to

    def test_model_upload_to_behaviour(self):
        # attach a file that exists by copying the image from the original source
        # 1. Copying an image file from the original source
        photo_file_path = self._copy_photo_file_to_media()
        try:
            obj: models.CVUserProfile = self.create_object()
            # same pattern as in `upload_to`
            dest_filename = self._get_photo_file_name(obj.user, photo_file_path.suffix)
            try:
                with self.assertRaises(ValueError) as exc:
                    self.assertIsNone(obj.photo.file)
                self.assertEqual('The \'photo\' attribute has no file associated with it.', str(exc.exception))

                obj.photo = photo_file_path.name
                obj.save()
                # and testing accessibility as obj.photo.file
                self.assertIsInstance(obj.photo.file, File)
                self.assertTrue(obj.photo.storage.exists(obj.photo.name))

                # 2. save via ImageField.save() will create file with name that defined by `upload_to` attribute
                accepted_filename = 'khjkhkj.jpg'
                with File(open(photo_file_path, 'rb'), name=accepted_filename) as f:
                    obj.photo = f
                    obj.save()

                # old file was deleted
                self.assertFalse(obj.photo.storage.exists(photo_file_path.name))
                # file with accepted_filename was not created
                self.assertFalse(obj.photo.storage.exists(accepted_filename))
                # new file was created
                self.assertTrue(obj.photo.storage.exists(dest_filename))

                # update file with other content
                orig_size = obj.photo.size
                with File(open(self.photo1_file_path_orig, 'rb'), name='dgsfgs.jpg') as f:
                    obj.photo = f
                    obj.save()

                # file with `dest_filename` exists
                self.assertTrue(obj.photo.storage.exists(dest_filename))
                # file was updated
                self.assertNotEqual(orig_size, obj.photo.storage.size(dest_filename))
            finally:
                # clearance
                obj.photo.storage.delete(dest_filename)
        finally:
            if photo_file_path.is_file():
                photo_file_path.unlink()

    def test_create_with_image_file(self):
        with self.assertRaises(PermissionDenied):
            super().test_create_with_image_file()

    def test_update_image_file(self):
        obj: models.CVUserProfile = self.create_object()
        request = self.get_request()

        storage: Storage = obj.photo.storage

        dst_filename = self._get_photo_file_name(request.user)
        # 2. Open image from original source and "upload"
        with File(open(self.photo_file_path_orig, 'rb'), name='rtrtyert.jpg') as f:
            ser = self.serializer_class(obj, data={'photo': f}, context={'request': request})
            is_valid = ser.is_valid()
            self.assertTrue(is_valid)
            ser.save()
        try:
            # to make sure the data is serialized appropriately
            self.assertDictEqual(ser.data, self.serialize_model_object(obj))

            # 3. file exists in destination
            self.assertEqual(str(obj.photo), dst_filename)
            self.assertTrue(storage.exists(dst_filename))
        finally:
            # 4. unlink
            storage.delete(dst_filename)


class TestResourcesSerializer(TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """
        Dictionary of available resources for all users, such as:
        'email' - contact, default login email
        'skype', 'site', 'linkedin', 'telegram',
        'telephone', 'upwork', 'facebook', 'tiktok',
        'instagram', 'tweeter', 'GitHub', 'GitLab' ....

        CVResources
            resource = models.CharField(max_length=24, unique=True)
    """

    serializer_class = serializers.ResourcesSerializer

    def get_model_kwargs(self) -> list[dict]:
        return [{'resource': 'email'}, {'resource': 'skype'}]

    @functools.cached_property
    def users(self) -> list[User]:
        user_model: User = models.get_user_model()
        return [
            user_model.objects.create_user(username='test_staff_user', email='test_staff_user@test.lan', is_staff=True),
            user_model.objects.create_user(username='test_user', email='test_user@test.lan')
        ]

    def get_request(self, user=None, method='get', method_data: dict = None):
        if user is None:
            user = self.users[0]
        return super().get_request(user, method, method_data)

    def get_bad_user(self):
        return self.users[1]

    def test_retrieve_bad_user(self):
        """
            Tests a success story for non-staff users.
            Retrieve is available for any users.
        """
        ser = self.serializer
        # create object for self.profile
        obj = self.create_object()
        # but try to work as self.bad_user_profile
        ser.context['request'] = self.get_request(self.get_bad_user())
        ser.instance = obj
        self.assertDictEqual(ser.data, self.serialize_model_object(obj))


class TestTechnologiesSerializer(TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """
        Dictionary like (for all users):
        'Python', 'SQL', 'Oracle' etc

        CVTechnologies:
            technology = models.CharField(max_length=24, unique=True)
    """

    serializer_class = serializers.TechnologiesSerializer

    def get_model_kwargs(self) -> list[dict]:
        return [{'technology': 'Python'}, {'technology': 'SQL'}]

    @functools.cached_property
    def users(self) -> list[User]:
        user_model: User = models.get_user_model()
        return [
            user_model.objects.create_user(username='test_staff_user', email='test_staff_user@test.lan', is_staff=True),
            user_model.objects.create_user(username='test_user', email='test_user@test.lan'),
            user_model.objects.create_user(username='test_profiled_user', email='test_profiled_user@test.lan')
        ]

    @functools.cached_property
    def profile(self) -> models.CVUserProfile:
        return models.CVUserProfile.objects.create(user=self.users[2])

    def get_request(self, user=None, method='get', method_data: dict = None):
        if user is None:
            user = self.users[0]
        return super().get_request(user, method, method_data)

    def get_bad_user(self):
        return self.users[1]

    def test_retrieve_bad_user(self):
        # Any users can retrieve data
        # test for registered not staff user
        with self.assertRaises(AssertionError, msg='PermissionDenied not raised') as exc:
            super().test_retrieve_bad_user()
        self.assertEqual(
            'PermissionDenied not raised',
            str(exc.exception),
            'Exception was raised dut it is not PermissionDenied'
        )

    def test_retrieve_ex(self):
        # Any users can retrieve data
        # test for AnonymousUser
        ser = self.serializer
        ser.context['request'] = super().get_request()
        obj = self.create_object()
        ser.instance = obj
        self.assertDictEqual(ser.data, self.serialize_model_object(obj))

    def post_test_create(self):
        # need to test if user is staff (staff used by default) then
        # serializers.TechnologiesSerializer.Meta.model.profile must be None
        self.assertIsNone(self.serializer.instance.profile)

    def test_create_ex(self):
        # if regular User then serializers.TechnologiesSerializer.Meta.model.profile must be setted
        ser = self.serializer

        for sub_msg, sub_r in (
                ('user is Anonymous -> PermissionDenied', super().get_request()),
                ('user has no profile -> PermissionDenied', self.get_request(self.users[1]))
        ):
            with self.subTest(sub_msg):
                ser.context['request'] = sub_r
                ser.initial_data = self.get_serializer_data()
                self.assertTrue(ser.is_valid())
                with self.assertRaises(PermissionDenied) as exc:
                    obj = ser.save()

        with self.subTest('user has profile'):
            ser.context['request'] = self.get_request(self.profile.user)
            ser.initial_data = self.get_serializer_data()
            self.assertTrue(ser.is_valid())
            obj: models.CVTechnologies = ser.save()
            self.assertIsNotNone(obj.pk)
            self.assertEqual(obj.profile, self.profile)
            self.assertDictEqual(ser.data, self.serialize_model_object(obj))

    def post_test_update(self):
        # update for staff -> test profile is None
        self.assertIsNone(self.serializer.instance.profile)

    def test_update_ex(self):
        ser: Serializer = self.serializer
        ser.context['request'] = self.get_request()  # for .users[0] -> no profile but staff

        # test technology is created by user and it updates by staff -> can change .profile to None
        obj = self.create_object(profile=self.profile)  # for .get_model_kwargs()[0] and .profile->.users[2]
        ser.instance = obj
        ser.initial_data = self.get_model_kwargs()[1] | {'profile': None}
        with self.subTest('Staff can change .profile to None'):
            self.assertIsNotNone(obj.profile)
            self.assertTrue(ser.is_valid())
            ser.save()
            self.assertIsNone(obj.profile)
            # to make sure the data is serialized appropriately
            self.assertDictEqual(ser.data, self.serialize_model_object(obj))

        # test technology is created by user and it updates by staff in other User -> can change .profile to other user
        profile_user1 = models.CVUserProfile.objects.create(user=self.users[1])
        obj.profile = profile_user1
        obj.save()
        self.assertNotEqual(self.profile, obj.profile)
        ser.__dict__.pop('_validated_data', None)
        ser.__dict__.pop('_data', None)
        ser.initial_data = self.get_model_kwargs()[0] | {'profile': self.profile.pk}
        with self.subTest('Staff can change .profile to other user'):
            self.assertTrue(ser.is_valid())
            ser.save()
            self.assertIsNotNone(obj.profile)
            self.assertEqual(self.profile, obj.profile)

            # to make sure the data is serialized appropriately
            self.assertDictEqual(ser.data, self.serialize_model_object(obj))

        # test technology that created by user and it updates by himself -> can change own technology
        ser.context['request'] = self.get_request(user=obj.profile.user)
        ser.initial_data = {'technology': 'TECH_WAS_CHANGED', 'profile': profile_user1.pk}
        self.assertNotEqual(obj.technology, ser.initial_data.get('tecnology'))
        self.assertEqual(ser.context['request'].user, ser.instance.profile.user)
        self.assertNotEqual(ser.initial_data.get('profile'), ser.instance.profile.pk)
        ser.__dict__.pop('_validated_data', None)
        ser.__dict__.pop('_data', None)
        with self.subTest('User can change data of himself'):
            self.assertTrue(ser.is_valid())
            ser.save()
            self.assertEqual(ser.context['request'].user, ser.instance.profile.user)
            self.assertNotEqual(profile_user1, obj.profile)

            obj.refresh_from_db()
            self.assertEqual(ser.initial_data['technology'], obj.technology)
            # to make sure the data is serialized appropriately
            self.assertDictEqual(ser.data, self.serialize_model_object(obj))

    def test_update_bad_user_ex(self):

        ser: Serializer = self.serializer
        ser.context['request'] = self.get_request(user=self.profile.user)  # for .users[2] -> regular user

        # test technology is created by user but other user try to update this technology
        # -> can't change .profile of other profile
        profile_user1 = models.CVUserProfile.objects.create(user=self.users[1])
        obj = self.create_object(profile=profile_user1)  # for .get_model_kwargs()[0] and .profile->.users[2]
        obj_profile_id = obj.profile_id
        ser.instance = obj
        ser.initial_data = self.get_model_kwargs()[1] | {'profile': self.profile.pk}
        with self.subTest('User can\'t change .profile of other profile'):
            self.assertNotEqual(self.profile, obj.profile)
            self.assertTrue(ser.is_valid())
            with self.assertRaises(PermissionDenied) as exc:
                ser.save()

            obj.refresh_from_db()
            self.assertEqual(obj_profile_id, obj.profile_id)

        # test technology is created by user and it updates by user but try to set other profile
        # -> can't change .profile to None or other profile

        obj.profile = self.profile
        obj.save()
        self.assertEqual(self.profile, obj.profile)
        ser.__dict__.pop('_validated_data', None)
        ser.__dict__.pop('_data', None)
        ser.initial_data = self.get_model_kwargs()[1] | {'profile': profile_user1.pk}
        with self.subTest('User can\'t change .profile to other profile'):
            self.assertTrue(ser.is_valid())
            self.assertNotEqual(ser.validated_data['profile'], ser.instance.profile)
            ser.save()
            obj.refresh_from_db()
            self.assertEqual(self.profile.pk, obj.profile_id)


class TestProjectTechnologySerializer(CVUserProfileMixin, TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """

        CVProjectTechnology:
            project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
            technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
            duration = models.DurationField(null=True, blank=True)
            notes = models.CharField(max_length=248)
    """

    serializer_class = serializers.ProjectTechnologySerializer

    @property
    def profile(self):
        return self.profiles[0]

    @functools.cached_property
    def projects(self):
        model = models.CVProject
        return [
            model.objects.create(
                profile=self.profile, begin=datetime.date(2010, 1, 1), end=datetime.date(2012, 3, 1),
                title='Some project title', description='Some project description',
                prerequisite='market requirements', result='is done'
            ),
            model.objects.create(
                profile=self.profile, begin=datetime.date(2012, 3, 2), end=datetime.date(2012, 7, 12),
                title='Next project title', description='Next project description',
                prerequisite='own needs', result='in process'
            ),
            # model.objects.create(
            #     profile=self.profile, begin=datetime.date(2010, 1, 1), end=None,
            #     title='Other project title', description='Other project description',
            #     prerequisite='Busyness', result='investigation'
            # ),
        ]

    @functools.cached_property
    def technologies(self) -> list[models.CVTechnologies]:
        model = models.CVTechnologies
        return [
            model.objects.create(technology='Python'),
            model.objects.create(technology='SQL'),
            model.objects.create(technology='Oracle')
        ]

    def get_model_kwargs(self) -> list[dict]:
        """
        technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
            { id, technology }
        duration = models.DurationField(null=True, blank=True)
        notes = models.CharField(max_length=248)
        """
        return [
            {'project': self.projects[0], 'technology': self.technologies[0],
             'duration': datetime.timedelta(15), 'notes': 'some Notes for 11111'},
            {'project': self.projects[0], 'technology': self.technologies[1],
             'duration': datetime.timedelta(15), 'notes': 'some Notes for 22222'},
            {'project': self.projects[0], 'technology': self.technologies[2],
             'duration': datetime.timedelta(15), 'notes': 'some Notes 33333'},
        ]

    def get_request(self, user=None, method='get', method_data: dict = None):
        return super().get_request(user or self.profile.user, method, method_data)

    def get_bad_user(self):
        return self.profiles[1].user

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        model_kwargs['technology'] = model_kwargs['technology'].pk
        model_kwargs['project'] = model_kwargs['project'].pk
        model_kwargs['duration'] = self.serializer.fields['duration'].to_representation(model_kwargs['duration'])
        return super().model_kwargs_to_serializer_data(model_kwargs)

    def serialize_model_object(self, obj: models.CVProjectTechnology, **kwargs):
        """
            Result should be:
            {
            'id': 1,
            'project': {'id': 1,'title': 'Some project title', 'description': 'Some project description', 'url': 'http://testserver/cv/api/profile/'},
            'technology': {'id': 1, 'technology': 'Python'},
            'duration': '15 00:00:00',
            'notes': 'some Notes for 11111'
            }
        """
        proj_data = {
            obj.project._meta.pk.column: obj.project.pk,
            'title': obj.project.title,
            self.serializer.url_field_name: reverse(self.serializer.project_view_name, request=self.serializer.context.get('request'))
        }

        tech_data = {
            obj.technology._meta.pk.column: obj.technology.pk,
            'technology': obj.technology.technology,
        }

        dur_data = self.serializer.fields['duration'].to_representation(obj.duration)
        res = super().serialize_model_object(
            obj, **kwargs | {'project': proj_data, 'technology': tech_data, 'duration': dur_data}
        )
        return res

    def _test_create_update_project_with_bad_user(self):
        """
            used in .test_create_project_with_bad_user and .test_update_project_with_bad_user
        """
        self.serializer.context['request'] = self.get_request()
        # get an update representation
        # self.create_object() returns an instance for self.get_model_kwargs()[0]
        # look at .test_update_project_with_bad_user
        data = self.model_kwargs_to_serializer_data(self.get_model_kwargs()[0])

        # create or get a project for different user
        bad_project = models.CVProject.objects.create(
            profile=self.profiles[2], begin=datetime.date(2010, 1, 1), end=None,
            title='Project title for different user', description='Project description for different user',
            prerequisite='Busyness', result='investigation'
        )
        data['project'] = bad_project.pk

        self.serializer.initial_data = data
        self.assertTrue(self.serializer.is_valid())
        with self.assertRaises(PermissionDenied) as exc:
            self.serializer.save()
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)

    def test_create_project_with_bad_user(self):
        self._test_create_update_project_with_bad_user()

    def test_update_project_with_bad_user(self):
        # Preparing the serializer for update. (.serializer is cached)
        obj = self.create_object()  # returns instance for self.get_model_kwargs()[0]
        self.serializer.instance = obj
        self._test_create_update_project_with_bad_user()


class TestWorkplaceResponsibilitySerializer(CVUserProfileMixin, TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """

        CVWorkplaceResponsibility
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
                {id: <int>, workplace = <str:248>, url: <str>}
            responsibility = models.TextField()
            role = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
    """

    serializer_class = serializers.WorkplaceResponsibilitySerializer

    @property
    def profile(self):
        return self.profiles[0]

    @functools.cached_property
    def workplaces(self):
        model = models.CVWorkplace
        return [
            model.objects.create(
                profile=self.profile, begin=datetime.date(2010, 1, 1), end=datetime.date(2012, 3, 1),
                workplace='Some workplace'
            ),
            model.objects.create(
                profile=self.profile, begin=datetime.date(2012, 3, 2), end=datetime.date(2012, 7, 12),
                workplace='Next workplace',
            )
        ]

    def get_model_kwargs(self) -> list[dict]:
        """
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
                {id: <int>, workplace = <str:248>, url: <str>}
            responsibility = models.TextField()
            role = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
        """
        return [
            {'workplace': self.workplaces[0], 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 1, 20),
             'responsibility': f'responsibility 111', 'role': 'manager'},
            {'workplace': self.workplaces[0], 'begin': datetime.date(2010, 1, 21), 'end': datetime.date(2012, 2, 10),
             'responsibility': f'responsibility 222', 'role': 'lead manager'},
            {'workplace': self.workplaces[0], 'begin': datetime.date(2010, 2, 11), 'end': datetime.date(2012, 3, 1),
             'responsibility': f'responsibility 333', 'role': 'deputy chief manager'},
        ]

    def get_request(self, user=None, method='get', method_data: dict = None):
        return super().get_request(user or self.profile.user, method, method_data)

    def get_bad_user(self):
        return self.profiles[1].user

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        model_kwargs['workplace'] = model_kwargs['workplace'].pk
        for be in ('begin', 'end'):
            model_kwargs[be] = self.serializer.fields[be].to_representation(model_kwargs[be])
        return super().model_kwargs_to_serializer_data(model_kwargs)

    def serialize_model_object(self, obj: models.CVWorkplaceResponsibility, **kwargs):
        """
            Result should be:
            {
            'id': 1,
            'workplace': {'id': 1, 'workplace': 'Some worlplace', 'url': 'http://testserver/cv/api/profile/'},
            'responsibility': 'responsibility 111',
            'role': 'manager'
            'begin': '2010-01-21'
            'end': '2012-01-20 00:00:00Z'
            }
        """
        wp = obj.workplace
        workplace_data = {
            wp._meta.pk.column: wp.pk,
            'workplace': wp.workplace,
            self.serializer.url_field_name: reverse(self.serializer.workplace_view_name, request=self.serializer.context.get('request'))
        }

        begin = self.serializer.fields['begin'].to_representation(obj.begin)
        end = self.serializer.fields['end'].to_representation(obj.end)

        res = super().serialize_model_object(
            obj, **kwargs | {'workplace': workplace_data, 'begin': begin, 'end': end}
        )
        return res

    def _test_create_update_with_bad_user(self, **data_kwargs):
        """
            used in .test_create_workplace_with_bad_user, .test_update_workplace_with_bad_user
            and ....
        """
        self.serializer.context['request'] = self.get_request()
        # get an update representation
        # self.create_object() returns an instance for self.get_model_kwargs()[0]
        # look at .test_update_workplace_with_bad_user
        data = self.model_kwargs_to_serializer_data(self.get_model_kwargs()[0])

        # init data for different user
        for f, v in data_kwargs.items():
            data[f] = v.pk

        self.serializer.initial_data = data
        self.assertTrue(self.serializer.is_valid())
        with self.assertRaises(PermissionDenied) as exc:
            self.serializer.save()
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)

    def _create_workplace_with_bad_user(self) -> models.CVWorkplace:
        return models.CVWorkplace.objects.create(
            profile=self.profiles[2], begin=datetime.date(2010, 1, 1), end=None,
            workplace='Workplace for different user'
        )

    def test_create_workplace_with_bad_user(self):
        self._test_create_update_with_bad_user(workplace=self._create_workplace_with_bad_user())

    def test_update_workplace_with_bad_user(self):
        # Preparing the serializer for update. (.serializer is cached)
        obj = self.create_object()  # returns instance for self.get_model_kwargs()[0]
        self.serializer.instance = obj
        self._test_create_update_with_bad_user(workplace=self._create_workplace_with_bad_user())

    def test_dates_range_crossing(self):
        # TODO: Probably need to remove. This case is tested in test_models_constraints.py
        obj = self.create_object()  # returns instance for self.get_model_kwargs()[0]
        with self.assertRaises(IntegrityError) as exc:
            obj1 = self.create_object(**self.get_model_kwargs()[1])
        self.assertEqual(
            'CHECK constraint failed: cv_cvworkplaceresponsibility_begin_end_date_range_intersection',
            str(exc.exception)
        )


class TestWorkplaceProjectSerializer(CVUserProfileMixin, TestRUBadUserMixin, TestCRUBaseSerializerMixin, APITestCase):
    """
        CVWorkplaceProject
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
                {id: <int>, workplace: <str:248>, begin: <datetime.date>, end: <datetime.date>, url: <str>}
            project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
                {id: <int>, title: <str:248>, begin: <datetime.date>, end: <datetime.date>, url: <str>}
    """

    serializer_class = serializers.WorkplaceProjectSerializer

    @property
    def profile(self):
        # default profile for .create_object()
        return self.profiles[0]

    @functools.cached_property
    def workplaces(self):
        """
            see .projects
        """
        model = models.CVWorkplace
        return [
            model.objects.create(
                profile=self.profile, begin=datetime.date(2010, 1, 1), end=datetime.date(2012, 3, 1),
                workplace='Some workplace'
            ),
            model.objects.create(
                profile=self.profile, begin=datetime.date(2012, 3, 2), end=datetime.date(2012, 7, 12),
                workplace='Next workplace',
            )
        ]

    @functools.cached_property
    def projects(self):
        """
            projects [0..1] for workplace[0]  and project[2] for workplace[1] same user (profile)
        """

        model = models.CVProject
        return [
            model.objects.create(
                profile=self.profile, begin=datetime.date(2010, 1, 1), end=datetime.date(2011, 2, 10),
                title='Some 1st project title', description='Some 1st project description',
                prerequisite='market requirements', result='is done'
            ),
            model.objects.create(
                profile=self.profile, begin=datetime.date(2011, 2, 11), end=datetime.date(2012, 2, 28),
                title='Some 2nd project title', description='Some 2nd project description',
                prerequisite='market requirements', result='is done'
            ),
            model.objects.create(
                profile=self.profile, begin=datetime.date(2012, 3, 2), end=datetime.date(2012, 7, 12),
                title='Next 1st project title', description='Next 1st project description',
                prerequisite='own needs', result='in process'
            ),
        ]

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'workplace': self.workplaces[0], 'project': self.projects[0]},
            {'workplace': self.workplaces[0], 'project': self.projects[1]},
            {'workplace': self.workplaces[1], 'project': self.projects[2]},
        ]

    def get_request(self, user=None, method='get', method_data: dict = None):
        return super().get_request(user or self.profile.user, method, method_data)

    def get_bad_user(self):
        return self.profiles[1].user

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        model_kwargs['workplace'] = model_kwargs['workplace'].pk
        model_kwargs['project'] = model_kwargs['project'].pk
        return super().model_kwargs_to_serializer_data(model_kwargs)

    def serialize_model_object(self, obj: models.CVWorkplaceResponsibility, **kwargs):
        """
            Result should be:
            {
            'id': 1,
            'workplace': {
                'id': 1,
                'workplace': 'Some worklplace',
                'begin': '2010-01-21',
                'end': '2012-01-20'
                'url': 'http://testserver/cv/api/profile/'},
            },
            'project': {
                'id': 1,
                'title': 'Some title',
                'begin': '2010-01-21',
                'end': '2012-01-20'
                'url': 'http://testserver/cv/api/profile/'},
            }
        """
        wp = obj.workplace
        wp_ser = serializers.WorkplaceSerializer()
        workplace_data = {
            wp._meta.pk.column: wp.pk,
            'workplace': wp.workplace,
            'begin': wp_ser.fields['begin'].to_representation(wp.begin),
            'end': wp_ser.fields['end'].to_representation(wp.end),
            self.serializer.url_field_name: reverse(
                self.serializer.workplace_view_name, request=self.serializer.context.get('request')
            )
        }

        proj = obj.project
        proj_ser = serializers.ProjectSerializer()
        project_data = {
            proj._meta.pk.column: proj.pk,
            'title': proj.title,
            'begin': proj_ser.fields['begin'].to_representation(proj.begin),
            'end': proj_ser.fields['end'].to_representation(proj.end),
            self.serializer.url_field_name: reverse(
                self.serializer.project_view_name, request=self.serializer.context.get('request'),
            )
        }
        res = super().serialize_model_object(
            obj, **kwargs | {'workplace': workplace_data, 'project': project_data}
        )
        return res

    def _create_project_with_bad_user(self) -> models.CVProject:
        model = models.CVProject
        return model.objects.create(
            profile=self.profiles[2], begin=datetime.date(2010, 1, 1), end=datetime.date(2011, 2, 10),
            title='Project title for different user', description='Project description for different user',
            prerequisite='market requirements', result='is done'
        )

    def test_create_workplace_with_bad_user(self):
        # To reuse code that already works, simply just need to invoke
        # the TestWorkplaceResponsibilitySerializer._test_create_update_with_bad_user
        # because it does not invoke supper() inside itself.
        TestWorkplaceResponsibilitySerializer._test_create_update_with_bad_user(
            self, workplace=TestWorkplaceResponsibilitySerializer._create_workplace_with_bad_user(self)
        )

    def test_update_workplace_with_bad_user(self):
        # Preparing the serializer for update. (.serializer is cached)
        obj = self.create_object()  # returns instance for self.get_model_kwargs()[0]
        self.serializer.instance = obj
        TestWorkplaceResponsibilitySerializer._test_create_update_with_bad_user(
            self, workplace=TestWorkplaceResponsibilitySerializer._create_workplace_with_bad_user(self)
        )

    def test_create_project_with_bad_user(self):
        TestWorkplaceResponsibilitySerializer._test_create_update_with_bad_user(
            self, project=self._create_project_with_bad_user()
        )

    def test_update_project_with_bad_user(self):
        # Preparing the serializer for update. (.serializer is cached)
        obj = self.create_object()  # returns instance for self.get_model_kwargs()[0]
        self.serializer.instance = obj
        TestWorkplaceResponsibilitySerializer._test_create_update_with_bad_user(
            self, project=self._create_project_with_bad_user()
        )
