# IDE: PyCharm
# Project: cv
# Path: apps/cv/tests
# File: test_serializers.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-07-18 (y-m-d) 9:06 AM
import datetime
import functools
from typing import Optional, Any, Callable, Type

from django.db import IntegrityError
from django.db.models import QuerySet, Model
from django.db.transaction import atomic
from django.forms import model_to_dict
from django.test import TestCase
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.reverse import reverse
from rest_framework.serializers import Serializer

from apps.cv import models, serializers
from rest_framework.test import APITestCase, APIClient, APIRequestFactory, force_authenticate


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


class CVUserProfileMixin:

    def get_profiles_kwargs(self) -> list[dict]:
        """
            CVUserProfile
                user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
                birthday = models.DateField(null=True, blank=True, default=None)
                photo = models.ImageField(null=True, blank=True)
        """

        user_kwrags = [
            {'username': 'test_dummy_user', 'email': 'test_dummy_user@cv_serializer.lan', 'password': '12345678'},
            {'username': 'test_user', 'email': 'test_user@cv_serializer.lan', 'password': '12345678'},
            {'username': 'test_some_user', 'email': 'test_some_user@cv_serializer.lan', 'password': '12345678'}
        ]
        return [{'user': args, 'birthday': None, 'photo': None} for args in user_kwrags]

    def get_profile_model(self) -> Type[models.CVUserProfile]:
        return models.CVUserProfile

    @functools.cached_property
    def profiles(self) -> list[models.CVUserProfile]:
        user_model = models.get_user_model()
        profile_model = self.get_profile_model()
        pkwargs = self.get_profiles_kwargs()
        return [profile_model.objects.create(user=user_model.objects.create_user(**pkw.pop('user'))) for pkw in pkwargs]


class TestBaseSerializer(CVUserProfileMixin, APITestCase):
    serializer_class = serializers.HobbySerializer

    @classmethod
    def setUpClass(cls):
        if not issubclass(cls.serializer_class, serializers.CVBaseSerializer):
            raise AssertionError(f'{cls.__name__}.serializer_class must be subclass serializers.CVBaseSerializer')
        super().setUpClass()

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVHobby
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                description = models.TextField(null=True, blank=True)
        """
        self.factory = APIRequestFactory()

    def test_request_required(self):
        with self.assertRaises(AssertionError) as exc:
            serializer = self.serializer_class(data={})
        self.assertEqual(self.serializer_class.assertion_messages['request_required'], str(exc.exception))

    def test_profile_required(self):
        request = self.factory.get('/')
        with self.assertRaises(AssertionError) as exc:
            serializer = self.serializer_class(object(), data={}, context={'request': request})
        self.assertEqual(self.serializer_class.assertion_messages['profile_required'], str(exc.exception))

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': 9999, 'description': 'Some description'},
            {'profile': 9999, 'description': 'Updated some description'},
            {'profile': 9999, 'description': None},
        ]

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        """
            It should be data that needs to Serializer(data=kwargs)
            model_kwargs is the data returned self.get_model_kwargs()
            It was used in:
                test_create(...)
                test_update(...)
                test_update_bad_user(...)

            mainly when the data for the Serializer should be generated
        """
        return model_kwargs

    def get_update_filed_names(self, serializer: Serializer) -> tuple:
        """
            Returns readonly Serializer fields by default.
            Used in:
                test_update(...)
                test_update_bad_user(...)
            as parameter for self.update_data_for_serializer(...)
        """
        return tuple(fn for fn, f in serializer.get_fields().items() if f.read_only is not True)

    def update_data_for_serializer(self, orig_data: dict, upd_data: dict, field_names: [tuple, list]) -> dict:
        """
            It should be data that needs to Serializer(data=kwargs)
            By default, it returns a copy of orig_data that has been updated by upd_data
            only for the fields passed as the field_names parameter.
            Used in:
                test_update(...)
                test_update_bad_user(...)
        """
        # get updated data as appropriate
        return orig_data | {fn: upd_data[fn] for fn in field_names if fn in upd_data}

    def get_serialized_instance(self, instance, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        ser = kwargs.pop('serializer', None)
        request = ser.context.get('request') if ser else None
        data = serialize_model_instance(instance, {
            'profile': lambda obj: reverse('cv:profile', request=request)
        })
        return data | {**kwargs}

    def test_check_owning(self):
        profile, dummy_profile = self.profiles[2], self.profiles[0]

        # authenticate as dummy_profile.user
        request = self.factory.put('/')
        request.user = dummy_profile.user

        # but try to work as profile
        ser = self.serializer_class(context={'request': request})
        ser.instance = self.serializer_class.Meta.model.objects.create(** self.get_model_kwargs()[0] | {'profile': profile})
        with self.assertRaises(PermissionDenied) as exc:
            ser.check_owning()
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)

    def test_retrieve(self):
        profile = self.profiles[2]

        # authenticate as profile.user
        request = self.factory.get('/')
        request.user = profile.user

        obj = self.serializer_class.Meta.model.objects.create(** self.get_model_kwargs()[0] | {'profile': profile})
        ser = self.serializer_class(obj, context={'request': request})
        self.assertDictEqual(ser.data, self.get_serialized_instance(obj, serializer=ser))

    def test_retrieve_bad_user(self):
        profile, dummy_profile = self.profiles[2], self.profiles[0]

        # authenticate as dummy_profile.user
        request = self.factory.get('/')
        request.user = dummy_profile.user

        # but try to work as profile
        obj = self.serializer_class.Meta.model.objects.create(** self.get_model_kwargs()[0] | {'profile': profile})
        ser = self.serializer_class(context={'request': request})
        ser.instance = obj
        with self.assertRaises(PermissionDenied) as exc:
            ser.data
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)

    def test_create(self):
        profile = self.profiles[2]

        # authenticate as profile.user
        request = self.factory.post('/')
        request.user = profile.user
        # `profile` can be anything because is readonly
        ser = self.serializer_class(
            data=self.model_kwargs_to_serializer_data(self.get_model_kwargs()[1]) | {'profile': 'ghdf'},
            context={'request': request}
        )
        self.assertTrue(ser.is_valid())
        obj = ser.save()
        self.assertIsNotNone(obj.pk)
        self.assertDictEqual(ser.data, self.get_serialized_instance(obj, serializer=ser))

        # test auto-filling of logged profile as profile field
        # this test allows to get rid of test_create_bad_user
        self.assertEqual(obj.profile, profile)

    def test_update(self):
        profile = self.profiles[2]

        request = self.factory.put('/')
        request.user = profile.user

        obj = self.serializer_class.Meta.model.objects.create(** self.get_model_kwargs()[0] | {'profile': profile})
        ser = self.serializer_class(obj, context={'request': request})
        orig_data = self.get_serialized_instance(obj, serializer=ser)

        data = self.update_data_for_serializer(
            self.model_kwargs_to_serializer_data(self.get_model_kwargs()[0]),
            self.model_kwargs_to_serializer_data(self.get_model_kwargs()[1]) | {'profile': profile},
            self.get_update_filed_names(ser)
        )
        ser.initial_data = data
        self.assertTrue(ser.is_valid())
        ser.save()
        # to make sure the data is serialized appropriately
        self.assertDictEqual(ser.data, self.get_serialized_instance(obj, serializer=ser))

        # to make sure the profile is the same
        self.assertEqual(obj.profile, profile)

    def test_update_bad_user(self):
        profile, dummy_profile = self.profiles[2], self.profiles[0]

        # authenticate as dummy_profile.user
        request = self.factory.put('/')
        request.user = dummy_profile.user

        # but try to work as profile
        obj = self.serializer_class.Meta.model.objects.create(** self.get_model_kwargs()[0] | {'profile': profile})

        # defer the PermissionDenied on the save() stage
        ser = self.serializer_class(context={'request': request})
        data = self.update_data_for_serializer(
            self.model_kwargs_to_serializer_data(self.get_model_kwargs()[0]),
            self.model_kwargs_to_serializer_data(self.get_model_kwargs()[1]) | {'profile': profile},
            self.get_update_filed_names(ser)
        )
        ser.instance = obj
        ser.initial_data = data
        self.assertTrue(ser.is_valid())
        with self.assertRaises(PermissionDenied) as exc:
            ser.save()
        self.assertEqual(exc.exception.default_code, PermissionDenied.default_code)


class TestHobbySerializer(TestBaseSerializer):
    serializer_class = serializers.HobbySerializer

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVHobby
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                description = models.TextField(null=True, blank=True)
        """
        super().setUp()

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'profile': 9999, 'description': 'Some description'},
            {'profile': 9999, 'description': 'Updated some description'},
            {'profile': 9999, 'description': None},
        ]


class TestLanguageSerializer(TestBaseSerializer):
    serializer_class = serializers.LanguageSerializer

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVLanguage
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                lang = models.CharField(max_length=24)
                level = models.CharField(max_length=24)
                notes = models.CharField(max_length=248)
        """
        super().setUp()

    def get_model_kwargs(self) -> list[dict]:
        return [
            {'profile': 9999, 'lang': 'English', 'level': 'Base', 'notes': 'Some notes'},
            {'profile': 9999, 'lang': 'UPD: English', 'level': 'Intermediate', 'notes': 'UPD: Some notes'},
            {'profile': 9999, 'lang': 'Ukraine', 'level': 'Native', 'notes': 'Some notes for Ukraine'},
        ]


# class TestUserRetrieveUpdateSerializer(TestBaseSerializer):
#     serializer_class = serializers.UserRetrieveUpdateSerializer
#
#     def setUp(self) -> None:
#         """
#             It must be tested on real serializer that is subclass serializers.CVBaseSerializer
#
#             django.contrib.auth.models.User
#                 fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
#                 read_only_fields = ['username', 'email', 'date_joined']
#         """
#         super().setUp()
#
#     def get_model_kwargs(self) -> list[dict]:
#         return [{'profile': 9999, **res} for res in self.resources]
#
#     def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
#         data = super().model_kwargs_to_serializer_data(model_kwargs)
#         data['resource'] = data['resource'].pk
#         return data
#
#     def get_serialized_instance(self, instance, **kwargs):
#         data = super().get_serialized_instance(instance, **kwargs)
#         data['resource'] = instance.resource.pk
#         return data
#


class TestUserResourceSerializer(TestBaseSerializer):
    serializer_class = serializers.UserResourceSerializer

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVUserResource
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                resource = models.ForeignKey(CVResources, on_delete=models.CASCADE)
                link = models.CharField(max_length=248)
        """
        super().setUp()

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
        return [{'profile': 9999, **res} for res in self.resources]

    def model_kwargs_to_serializer_data(self, model_kwargs: dict) -> dict:
        data = super().model_kwargs_to_serializer_data(model_kwargs)
        data['resource'] = data['resource'].pk
        return data

    def get_serialized_instance(self, instance, **kwargs):
        data = super().get_serialized_instance(instance, **kwargs)
        data['resource'] = instance.resource.pk
        return data


class TestEducationSerializer(TestBaseSerializer):
    serializer_class = serializers.EducationSerializer

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVEducation
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                begin = models.DateField(default=datetime.date.today)
                end = models.DateField(null=True, default=None, blank=True)
                institution = models.CharField(max_length=248)
                speciality = models.CharField(max_length=248)
                degree = models.CharField(max_length=24)
                complete = models.BooleanField(default=True)
        """
        super().setUp()

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': 9999, 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 3, 1),
             'institution': 'Some university', 'speciality': 'Computer science', 'degree': 'Bachelor', 'complete': True},
            {'profile': 9999, 'begin': datetime.date(2012, 3, 1), 'end': datetime.date(2012, 7, 12),
             'institution': 'Next university', 'speciality': 'Computer science', 'degree': 'Master', 'complete': True},
            {'profile': 9999, 'begin': datetime.date(2010, 1, 1), 'end': None,
             'institution': 'Other university', 'speciality': 'Busyness', 'degree': 'Master', 'complete': True},
        ]

    def get_serialized_instance(self, instance, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        data = super().get_serialized_instance(instance, **kwargs)
        data['begin'] = str(instance.begin)
        data['end'] = str(instance.end)
        return data

    # TODO: Probably need to add the date range crossing tests


class TestProjectSerializer(TestBaseSerializer):
    serializer_class = serializers.ProjectSerializer

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVProject
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                description = models.CharField(max_length=248)
                prerequisite = models.CharField(max_length=248)
                result = models.CharField(max_length=48)
                begin = models.DateField(default=datetime.date.today)
                end = models.DateField(null=True, default=None, blank=True)
        """
        super().setUp()

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': 9999, 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 3, 1),
             'description': 'Some project description', 'prerequisite': 'market requirements', 'result': 'is done'},
            {'profile': 9999, 'begin': datetime.date(2012, 3, 1), 'end': datetime.date(2012, 7, 12),
             'description': 'Next project description', 'prerequisite': 'own needs', 'result': 'in process'},
            {'profile': 9999, 'begin': datetime.date(2010, 1, 1), 'end': None,
             'description': 'Other project description', 'prerequisite': 'Busyness', 'result': 'investigation'},
        ]

    def get_serialized_instance(self, instance, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        data = super().get_serialized_instance(instance, **kwargs)
        data['begin'] = str(instance.begin)
        data['end'] = str(instance.end)
        return data

    # TODO: Probably need to add the date range crossing tests


class TestWorkplaceSerializer(TestBaseSerializer):
    serializer_class = serializers.WorkplaceSerializer

    def setUp(self) -> None:
        """
            It must be tested on real serializer that is subclass serializers.CVBaseSerializer

            CVWorkplace:
                profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
                workplace = models.CharField(max_length=248)
                begin = models.DateField(default=datetime.date.today)
                end = models.DateField(null=True, default=None, blank=True)
        """
        super().setUp()

    def get_model_kwargs(self) -> list[dict]:
        """
            returns dict to create model instance (model of tested Serializer or APIView)
            It should be data that needs to model.objects.create(**kwargs)
        """
        return [
            {'profile': 9999, 'begin': datetime.date(2010, 1, 1), 'end': datetime.date(2012, 3, 1),
             'workplace': 'Electrotyazghmash plant'},
            {'profile': 9999, 'begin': datetime.date(2012, 3, 1), 'end': datetime.date(2012, 7, 12),
             'workplace': 'Kharkiv Customs'},
            {'profile': 9999, 'begin': datetime.date(2010, 1, 1), 'end': None,
             'workplace': 'Freelancer'},
        ]

    def get_serialized_instance(self, instance, **kwargs):
        """
            returns data to represent model data
            It should be data that expects to test with serializer.data
        """
        data = super().get_serialized_instance(instance, **kwargs)
        data['begin'] = str(instance.begin)
        data['end'] = str(instance.end)
        return data

    # TODO: Probably need to add the date range crossing tests
