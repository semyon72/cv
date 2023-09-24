# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: serializers.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-06-23 (y-m-d) 7:09 AM
import functools
import base64
from typing import Union

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import IntegrityError
from django.db.models import Model

from rest_framework.exceptions import PermissionDenied, NotAuthenticated, ValidationError
from rest_framework.fields import empty
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, FileUploadParser, JSONParser, BaseParser
from rest_framework.request import Request
from rest_framework.reverse import reverse
from rest_framework.serializers import Serializer

from PIL import Image

from . import models

from rest_framework import serializers, settings


def get_user_profile(request: Request) -> models.CVUserProfile:
    if not request.user.is_authenticated:
        raise NotAuthenticated()
    return get_object_or_404(models.CVUserProfile, user=request.user)


def catch_integrity_raise_validation(ser: Serializer, cback, *cback_args, **cback_kwargs):
    # tests that `cback` is not bound to an instance.
    args = []
    slf = getattr(cback, '__self__', None)
    if slf is None:
        args.append(ser)

    args.extend(cback_args)
    try:
        result = cback(*args, **cback_kwargs)
    except IntegrityError as exc:
        super(Serializer, ser).errors.update({
            settings.api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]
        })
        raise ValidationError(ser.errors)

    return result


class IntegrityToValidation:
    """
        It will only work properly if you need to encapsulate entire `update` or `create` code
        in a try: ... except IntegrityError: ... block.

        But if you need to do pre-checks that will raise some exception before the `create` or `update` action
        to prevent them - it will not work properly.
    """

    error_msg = 'integrity_to_validation decorator applicable only for Serializer.create or .update'

    def __init__(self, create_or_update_func) -> None:
        self.create_or_update_func = create_or_update_func

    def __set_name__(self, owner, name):
        if not issubclass(owner, Serializer) or name not in ('create', 'update'):
            raise ValueError(self.error_msg)

    def __get__(self, instance, owner=None):
        self.serializer = instance
        return self

    def __call__(self, *args, **kwargs):
        """
            args[0] - serializer instance
            args[1] - for create is validated_data
            args[1] - for update is instance
            args[2] - for update is validated_data

            ** kwargs - is not using
        """
        return catch_integrity_raise_validation(self.serializer, self.create_or_update_func, *args, **kwargs)


def _has_request(serializer: Serializer, msg: str = None):
    """
        Used in .check_xxx_owning to test Serializer(....) has .context['request']
    """
    if not msg:
        msg = "Request is required. Make sure context={'request': request} is passed to the serializer"

    request = serializer.context.get('request', None)
    if request is None:
        raise AssertionError(msg)


class CVBaseSerializer(serializers.ModelSerializer):

    assertion_messages = {
        'request_required': "Request is required. Make sure context={'request': request} is passed to the serializer",
        'profile_required': "This serializer is only applicable to instances with the `profile` attribute",
    }

    view_name = 'cv:profile'
    profile = serializers.SerializerMethodField()

    def _has_request(self):
        """
            Used in .check_owning and .create (via .set_default_profile)
            to test Serializer(....) has .context['request']
        """
        _has_request(self, CVBaseSerializer.assertion_messages['request_required'])

    def _has_instance_profile(self, instance):
        """
            Used in .check_owning to test Serializer(....) .instance has .profile field
            by default it will test instance.profile against request['user']
        """
        if not hasattr(instance, 'profile'):
            raise AssertionError(self.assertion_messages['profile_required'])

    def get_profile(self, obj):
        return reverse(self.view_name, request=self.context.get('request'))

    def check_owning(self, instance):
        self._has_request()
        self._has_instance_profile(instance)

        if instance.profile != get_user_profile(self.context['request']):
            raise PermissionDenied()

    def to_representation(self, instance):
        self.check_owning(instance)
        return super(CVBaseSerializer, CVBaseSerializer).to_representation(self, instance)

    def validate_action(self, cback: callable, *cback_args, **cback_kwargs):
        try:
            result = cback(*cback_args, **cback_kwargs)
        except IntegrityError as exc:
            super(Serializer, self).errors.update({
                settings.api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]
            })
            raise ValidationError(self.errors)

        return result

    def update(self, instance, validated_data):
        # to eliminate mistakes in permissions, additional clearance.
        validated_data.pop('profile', None)
        self.check_owning(instance)

        instance = self.validate_action(
            functools.partial(super(CVBaseSerializer, CVBaseSerializer).update, self), instance, validated_data
        )
        return instance

    def set_default_profile(self, validated_data):
        """
            Used only in .create
        """
        self._has_request()
        validated_data['profile'] = get_user_profile(self.context['request'])

    def create(self, validated_data):
        # to eliminate mistakes in permissions, additional clearance.
        self.set_default_profile(validated_data)
        instance = self.validate_action(
            functools.partial(super(CVBaseSerializer, CVBaseSerializer).create, self), validated_data
        )

        return instance


class EducationSerializer(CVBaseSerializer):

    class Meta:
        model = models.CVEducation
        fields = '__all__'


class HobbySerializer(CVBaseSerializer):

    class Meta:
        model = models.CVHobby
        fields = '__all__'


class LanguageSerializer(CVBaseSerializer):

    class Meta:
        model = models.CVLanguage
        fields = '__all__'


class ProjectSerializer(CVBaseSerializer):

    class Meta:
        model = models.CVProject
        fields = '__all__'


class CVBaseReadonlyOrAdminSerializer(serializers.ModelSerializer):

    _has_request = CVBaseSerializer._has_request

    def check_save_permission(self):
        self._has_request()
        user: User = self.context['request'].user
        if not (user.is_authenticated and user.is_staff):
            raise PermissionDenied()

    def save(self):
        self.check_save_permission()
        return super().save()


class ResourcesSerializer(CVBaseReadonlyOrAdminSerializer):
    """
        Support access readonly-for_all or write-staff_user
    """
    class Meta:
        model = models.CVResources
        fields = '__all__'


class TechnologiesSerializer(CVBaseReadonlyOrAdminSerializer):
    """
        Support access readonly-for_all or write-staff_user
    """

    class Meta:
        model = models.CVTechnologies
        fields = '__all__'


class ProjectTechnologySerializer(serializers.ModelSerializer):
    """
    CVProjectTechnology
        id
        project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
            { id, profile -> url, description, prerequisite, result, begin, end }
        technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
            { id, technology }
        duration = models.DurationField(null=True, blank=True)
        notes = models.CharField(max_length=248)
    """
    project_view_name = 'cv:project'

    class Meta:
        model = models.CVProjectTechnology
        fields = '__all__'

    def check_project_owning(self, *projects):
        _has_request(self)
        user_profile = get_user_profile(self.context['request'])
        for project in projects:
            if project.profile != user_profile:
                raise PermissionDenied()

    def get_project_representation(self, obj: models.CVProjectTechnology):
        project = obj.project
        res = {
            project._meta.pk.column: project.pk,
            'description': project.description,
            self.url_field_name: reverse(self.project_view_name, request=self.context.get('request'))
        }
        return res

    def get_technology_representation(self, obj: models.CVProjectTechnology):
        return {
            obj.technology._meta.pk.column: obj.technology.pk,
            'technology': obj.technology.technology,
        }

    def to_representation(self, instance: models.CVProjectTechnology):
        self.check_project_owning(instance.project)
        data = super().to_representation(instance)
        data['project'] = self.get_project_representation(instance)
        data['technology'] = self.get_technology_representation(instance)
        return data

    def validate_action(self, cback: callable, *cback_args, **cback_kwargs):
        try:
            result = cback(*cback_args, **cback_kwargs)
        except IntegrityError as exc:
            super(Serializer, self).errors.update({
                settings.api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]
            })
            raise ValidationError(self.errors)

        return result

    def update(self, instance: models.CVProjectTechnology, validated_data: dict):
        self.check_project_owning(instance.project, validated_data.get('project'))
        return catch_integrity_raise_validation(self, super().update, instance, validated_data)

    def create(self, validated_data: dict):
        self.check_project_owning(validated_data.get('project'))
        return catch_integrity_raise_validation(self, super().create, validated_data)


class UserRetrieveUpdateSerializer(CVBaseSerializer):

    # We remove 'profile' by default (it inherits),
    # but it appears in default representation if self.parent is None.
    # Therefore, if a Serializer is used as a field then 'profile' will be omitted.
    profile = None

    class Meta:
        model = models.get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['username', 'email', 'date_joined']

    def create(self, validated_data):
        # TODO: How to display login and signup urls for redirect (best way)?
        # raise PermissionDenied(['User creation is prohibited', ...])
        # detail can be list, by default it is PermissionDenied.default_detail
        raise PermissionDenied(['User creation is prohibited', 'Sign In: ......', 'Sign Up: ......'])

    def check_owning(self, user):
        # This logic is equal to the original CVBaseSerializer._has_request()
        # but because we will need the `request` object later here we repeat the code of it, almost
        request = self.context.get('request', None)
        if request is None:
            raise AssertionError(CVBaseSerializer.assertion_messages['request_required'])

        # to eliminate mistakes in permissions, additional clearing.
        if user is None:
            user = self.instance

        if user != request.user:
            raise PermissionDenied()

    def validate_action(self, cback: callable, *cback_args, **cback_kwargs):
        # stub for CVBaseSerializer.update
        # It just run cback (original serializers.ModelSerializer.update)
        # without any CVBaseSerializer.validate_action instruction because it User that has no additional checks etc.
        return cback(*cback_args, **cback_kwargs)

    def to_representation(self, instance) -> dict:
        res = super().to_representation(instance)
        if self.parent is None:
            res['profile'] = self.get_profile(instance)
        else:
            res[self.url_field_name] = reverse('cv:user', request=self.context['request'])
        return res


class ProfileSerializer(serializers.ModelSerializer):
    """
        It supports create, update, retrieve actions without 'photo' field as JSON
        If you need (want) upload 'photo' also in one request then should be used
        'multipart/form-data; boundary=SoMeBoUnDaRyStRiNg'.
        Other, file uploading cases are supported by ProfilePhotoSerializer
    """
    user = UserRetrieveUpdateSerializer(read_only=True)

    class Meta:
        model = models.CVUserProfile
        fields = ['id', 'user', 'birthday', 'photo']

    def check_owning(self, profile: models.CVUserProfile):
        request = self.context.get('request', None)
        if request is None:
            raise AssertionError(CVBaseSerializer.assertion_messages['request_required'])

        # to eliminate mistakes in permissions, additional clearing.
        if profile is None:
            profile = self.instance

        if profile.user != self.context['request'].user:
            raise PermissionDenied()

    # CVBaseSerializer.to_representation - returns standard serializers.ModelSerializer.to_representation
    # with check for owning
    to_representation = CVBaseSerializer.to_representation

    @functools.cached_property
    def selected_parser(self) -> BaseParser:
        request = self.context['request']
        # request.negotiator is a child instance of BaseContentNegotiation
        # Under the hood it compares
        # request.parsers[x].media_type  # 'application/json'
        # with
        # request.content_type  # 'multipart/form-data; boundary=BoUnDaRyStRiNg'
        parser = request.negotiator.select_parser(request, request.parsers)
        return parser

    def photo_base64_to_file(self, data: dict):
        photo_b64 = data.get('photo')
        if not photo_b64 or isinstance(photo_b64, File):
            return

        # It is probably better to put this implementation in a dedicated JSONParser, but for now ...
        file = ContentFile(base64.b64decode(photo_b64))
        with Image.open(file) as img:
            img_format = img.format.lower()
            file.seek(0)
        request = self.context['request']
        file_name = request.parser_context['kwargs'].get('filename')
        if not file_name:
            file.name = f"{request.user.username}_{request.user.pk}.{img_format}"
        data['photo'] = file

    def to_internal_value(self, data):
        if isinstance(self.selected_parser, JSONParser):
            # It is probably better to put this implementation in a dedicated JSONParser, but for now ...
            self.photo_base64_to_file(data)

        return super().to_internal_value(data)

    def create(self, validated_data):
        # We explicitly set the user that was logged
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, profile, validated_data):
        # to eliminate mistakes in permissions, additional clearance.
        user = validated_data.pop('user', None)
        self.check_owning(profile)

        return super().update(profile, validated_data)


class ProfilePhotoSerializer(ProfileSerializer):
    """
        Like a ProfileSerializer with next differences:
            Doesn't allow create profile
            Doesn't allow modify any fields exclude `photo`
            It supports MultiPartParser, FileUploadParser, JSONParser (in this order)
            content of `photo` must be base64 encoded for JSONParser
    """

    class Meta(ProfileSerializer.Meta):
        fields = ['id', 'user', 'birthday', 'photo']
        readonly = ['id', 'user', 'birthday']

    def to_internal_value(self, data):
        parser = self.selected_parser

        assert isinstance(
            parser, (FileUploadParser, JSONParser, MultiPartParser)
        ), f"Parser '{parser.__class__.__name__}' is not supported"

        # JSONParser is implemented in parent

        if isinstance(parser, FileUploadParser):
            # because standard to_internal_value is waiting data['photo'] key
            # but FileUploadParser returns image (file) under data['file']
            # we will create - reference if File object
            data['photo'] = data['file']

        return super().to_internal_value(data)

    def update(self, profile, validated_data: dict):
        validated_data = {'photo': validated_data.get('photo')}
        return super().update(profile, validated_data)

    def create(self, validated_data: dict):
        # TODO: How to display login and signup urls for redirect (best way)?
        raise PermissionDenied([
            'Profile creation is prohibited, use PUT action',
            'Sign In: ......',
            'Sign Up: ......'
        ])


class UserResourceSerializer(CVBaseSerializer):

    class Meta:
        model = models.CVUserResource
        fields = '__all__'


class WorkplaceSerializer(CVBaseSerializer):

    class Meta:
        model = models.CVWorkplace
        fields = '__all__'


class WorkplaceProjectSerializer(serializers.ModelSerializer):
    """
        CVWorkplaceProject
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
                {id: <int>, workplace: <str:248>, begin: <datetime.date>, end: <datetime.date>, url: <str>}
            project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
                {id: <int>, description: <str:248>, begin: <datetime.date>, end: <datetime.date>, url: <str>}
    """
    workplace_view_name = 'cv:workplace'
    project_view_name = 'cv:project'

    class Meta:
        model = models.CVWorkplaceProject
        fields = '__all__'

    def get_workplace_representation(self, workplace: models.CVWorkplace):
        # This approach relies on the implementation of the WorkplaceSerializer representation.
        # Another approach, see in the WorkplaceResponsibilitySerializer.get_workplace_representation.
        req = self.context.get('request')
        res = {f: v for f, v in WorkplaceSerializer(
            workplace,
            read_only=True,
            context={'request': req}
        ).data.items() if f in ('id', 'workplace', 'begin', 'end')}
        res[self.url_field_name] = reverse(self.workplace_view_name, request=req)
        return res

    def get_project_representation(self, project: models.CVProject):
        # This approach relies on the implementation of the ProjectSerializer representation.
        # Another approach, see in the WorkplaceResponsibilitySerializer.get_workplace_representation.
        req = self.context.get('request')
        res = {f: v for f, v in ProjectSerializer(
            project,
            read_only=True,
            context={'request': req}
        ).data.items() if f in ('id', 'description', 'begin', 'end')}
        res[self.url_field_name] = reverse(self.project_view_name, request=req)
        return res

    def check_owning(self, *profiled_instances: Model):
        _has_request(self)
        user_profile = get_user_profile(self.context['request'])

        for instance in profiled_instances:
            if instance.profile != user_profile:
                raise PermissionDenied()

    def to_representation(self, instance: models.CVWorkplaceProject):
        self.check_owning(instance.workplace, instance.project)
        res = super().to_representation(instance)
        res['workplace'] = self.get_workplace_representation(instance.workplace)
        res['project'] = self.get_project_representation(instance.project)
        return res

    def create(self, validated_data):
        self.check_owning(validated_data.get('workplace'), validated_data.get('project'))
        return catch_integrity_raise_validation(self, super().create, validated_data)

    def update(self, instance: models.CVWorkplaceProject, validated_data: dict):
        self.check_owning(
            instance.workplace, instance.project, validated_data.get('workplace'), validated_data.get('project')
        )
        return catch_integrity_raise_validation(self, super().update, instance, validated_data)


class WorkplaceResponsibilitySerializer(serializers.ModelSerializer):
    """
        CVWorkplaceResponsibility
            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
                {id: <int>, workplace = <str:248>, url: <str>}
            responsibility = models.TextField()
            role = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
    """
    workplace_view_name = 'cv:workplace'

    class Meta:
        model = models.CVWorkplaceResponsibility
        fields = '__all__'

    def get_workplace_representation(self, workplace: models.CVWorkplace):
        # This approach does not rely on an implementation of the WorkplaceSerializer representation.
        # Another approach, see in the WorkplaceProjectSerializer.get_workplace_representation.
        res = {
            workplace._meta.pk.column: workplace.pk,
            'workplace': workplace.workplace,
            self.url_field_name: reverse(self.workplace_view_name, request=self.context.get('request'))

        }
        return res

    def check_workplace_owning(self, *workplaces: models.CVWorkplace):
        _has_request(self)
        user_profile = get_user_profile(self.context['request'])
        for workplace in workplaces:
            if workplace.profile != user_profile:
                raise PermissionDenied()

    def to_representation(self, instance: models.CVWorkplaceResponsibility):
        self.check_workplace_owning(instance.workplace)
        data = super().to_representation(instance)
        data['workplace'] = self.get_workplace_representation(instance.workplace)
        return data

    def create(self, validated_data):
        self.check_workplace_owning(validated_data.get('workplace'))
        return catch_integrity_raise_validation(self, super().create, validated_data)

    def update(self, instance: models.CVWorkplaceResponsibility, validated_data: dict):
        self.check_workplace_owning(instance.workplace, validated_data.get('workplace'))
        return catch_integrity_raise_validation(self, super().update, instance, validated_data)

