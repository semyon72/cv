from typing import Optional, Iterable

from django.contrib.auth.models import User
from django.db.models import Model, QuerySet, Q, F
from django.http import Http404
from django.shortcuts import render

# Create your views here.
from django.urls import get_resolver, get_ns_resolver
from drf_spectacular.plumbing import get_doc

from rest_framework import generics, mixins, parsers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import BaseFilterBackend
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import (IsAuthenticated, BasePermission, SAFE_METHODS, IsAdminUser, )
from rest_framework.response import Response
from rest_framework.reverse import reverse

from . import serializers, models

# Staff (common for all)
# class Resources:
# class Technologies:

# User (should be authenticated)
# class User:
# class UserResource:
# class Education:
# class Hobby:
# class Language:
# class Project:
# class Workplace:

# No User but has relation via other tables
# class ProjectTechnology <- class Project:
# class WorkplaceProject <- class Workplace:
# class Workplace <- class WorkplaceResponsibilitySerializer -> class Project:
from .models import CVUserProfile
from . import schemas


class IsReadOnlyOrAdmin(BasePermission):
    """
    The request is authenticated as a staff user, or is a read-only request.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS or
            (request.user and request.user.is_staff)
        )


class TechnologyPermission(BasePermission):

    def has_permission(self, request, view) -> bool:
        """
            retrieve for all and modification for registered users only
        """
        return request.method in SAFE_METHODS or (request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj: models.CVTechnologies) -> bool:
        # The next permissions were narrowed on previous step (in .has_permission)
        # - Read only for safe methods
        # - For unsafe methods, the unauthenticated users can't do any actions

        # staff can do any actions
        if request.user.is_staff:
            return True

        if request.method in SAFE_METHODS:
            # an authenticated user can see public (.profile is None) and their own technologies
            return obj.profile is None or obj.profile.user == request.user
        else:
            # an authenticated user can only operate on their own technologies
            return obj.profile is not None and obj.profile.user == request.user


class IsReadOnly(BasePermission):
    """
    The request is a read-only request.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS
        )


class IsAuthenticatedAndMyself(BasePermission):
    """
    The request is authenticated and try to get object for current logged user.
    """

    def get_obj_user(self, obj):
        if type(obj) is serializers.UserRetrieveUpdateSerializer.Meta.model:
            return obj

        if type(obj) is serializers.ProfileSerializer.Meta.model:
            return obj.user

        if type(obj) is serializers.WorkplaceProjectSerializer.Meta.model:
            if obj.workplace.profile != obj.project.profile:
                return None
            else:
                return obj.workplace.profile.user

        if type(obj) is serializers.ProjectTechnologySerializer.Meta.model:
            obj = obj.project

        if type(obj) is serializers.WorkplaceResponsibilitySerializer.Meta.model:
            obj = obj.workplace

        p = getattr(obj, 'profile', None)
        if p is not None:
            return p.user

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        obj_user = self.get_obj_user(obj)
        if obj_user is None:
            return False
        return bool(obj_user == request.user)


def get_current_profile(request, raise_not_found=True) -> Optional[CVUserProfile]:
    profile = CVUserProfile.objects.select_related('user').filter(user=request.user)
    if len(profile) == 1:
        return profile[0]
    if raise_not_found:
        if len(profile) == 0:
            error = "%s not found" % CVUserProfile._meta.object_name
        else:
            error = "Weird, more than 1 instance of the %s was found." % CVUserProfile._meta.object_name
        raise Http404(error)


class PermitAuthenticatedMixin:
    permission_classes = [IsAuthenticated]


# Views

class UserRetrieveUpdate(PermitAuthenticatedMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.UserRetrieveUpdateSerializer
    queryset = serializers.UserRetrieveUpdateSerializer.Meta.model

    def get_object(self):
        # fix for retrieve the current user for url that does not contains URL keyword argument
        self.kwargs[self.lookup_field] = self.request.user.pk
        return super().get_object()


class ProfilePhotoUpdate(PermitAuthenticatedMixin, generics.UpdateAPIView):
    """
        It allows update only `photo` field and return representation like a regular
        serializers.ProfileSerializer

        1. serializers.ProfileSerializer used as read-only
        2. serializer = self.get_serializer(instance)

    """

    permission_classes = [IsAuthenticatedAndMyself]
    # order of Parsers is important, if parsers.FileUploadParser is first
    # then it will always be used because FileUploadParser.media_type = '*/*'
    parser_classes = [parsers.MultiPartParser, parsers.JSONParser, parsers.FileUploadParser]

    serializer_class = serializers.ProfilePhotoSerializer
    queryset = serializer_class.Meta.model.objects.select_related('user')

    def get_object(self):
        # fix for retrieve the current profile for url that does not contains URL keyword argument
        self.kwargs[self.lookup_field] = get_current_profile(self.request).pk
        return super().get_object()


class ResourcesListCreate(generics.ListCreateAPIView):
    permission_classes = [IsReadOnly | IsAdminUser]
    serializer_class = serializers.ResourcesSerializer
    queryset = serializers.ResourcesSerializer.Meta.model.objects.all()


class ResourcesRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsReadOnlyOrAdmin]
    serializer_class = serializers.ResourcesSerializer
    queryset = serializers.ResourcesSerializer.Meta.model.objects.all()


class TechnologiesListCreate(generics.ListCreateAPIView):
    permission_classes = [TechnologyPermission]
    serializer_class = serializers.TechnologiesSerializer
    queryset = serializers.TechnologiesSerializer.Meta.model.objects.all()

    def get_queryset(self):
        q = super(TechnologiesListCreate, TechnologiesListCreate).get_queryset(self)
        u: User = self.request.user
        q_for_all = Q(profile__isnull=True)
        if not u.is_authenticated:
            q = q.filter(q_for_all)
        elif not u.is_staff:
            q = q.filter(q_for_all | Q(profile__user=u))
        # else:
        #     # staff can change all technologies
        #     pass
        return q


class TechnologiesRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [TechnologyPermission]
    serializer_class = serializers.TechnologiesSerializer
    queryset = serializers.TechnologiesSerializer.Meta.model.objects.all()

    get_queryset = TechnologiesListCreate.get_queryset


class MyselfFilter(BaseFilterBackend):

    def filter_queryset(self, request, queryset: QuerySet, view):
        profile = get_current_profile(request)
        if issubclass(type(view), WorkplaceProject):
            rqs = queryset.filter(workplace__profile=profile, project__profile=F('workplace__profile'))
        elif issubclass(type(view), WorkplaceResponsibility):
            rqs = queryset.filter(workplace__profile=profile)
        elif issubclass(type(view), ProjectTechnology):
            rqs = queryset.filter(project__profile=profile)
        else:
            rqs = queryset.filter(profile=profile)
        return rqs


class CVBaseAPIView(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    """
        Implements base behaviour for List, Create, Retrieve, Update, Partial-Update, Delete.
        It should be coupled with URLs definition like
        re_path('^education/(?:(?P<pk>[0-9]+)/)?$', Education.as_view(), name='education') where `pk` is optional part.
        It will respond to the URLs "education/1222/" or "education/".
    """

    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = None

    def _initialize_queryset(self):
        """
            Initialize self.queryset from self.serializer_class
        """
        if self.queryset is None:
            # try to from serializer
            model: Model = self.serializer_class.Meta.model
            self.queryset = model.objects.all()

    def _get_lookup_field_name(self) -> str:
        return self.lookup_url_kwarg or self.lookup_field

    def _prepare_lookup_field(self) -> Optional[int]:
        # It converts `pk` value into int
        lookup_url_kwarg = self._get_lookup_field_name()
        pk = self.kwargs.get(lookup_url_kwarg, None)
        if pk is not None:
            self.kwargs[lookup_url_kwarg] = int(pk)
        return pk

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._prepare_lookup_field()
        self._initialize_queryset()

    def get(self, request, *args, **kwargs):
        """
            We must take decision on self.args or self.kwargs, Is 'GET' request either list or retrieve?
            It should be coupled with urls definition like
            re_path('^education/(?:(?P<pk>[0-9]+)/)?$', Education.as_view(), name='education')
            where `pk` is optional part
        """
        lookup_url_kwarg = self._get_lookup_field_name()
        # We did some preparation in .initial
        if lookup_url_kwarg in self.kwargs:
            return self.retrieve(request, *args, **kwargs)
        else:
            return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def options(self, request, *args, **kwargs):
        # Issue - Inside super will be checking (testing) the PUT and POST actions,
        # literally in SimpleMetadata.determine_actions(...)
        # but for PUT case it checks self.lookup_field by self.get_object()
        #
        # Cases to resolve:
        # 1. temporary remove the 'PUT' from self.http_method_names
        # 2. temporary add a stub for `get_object` method which will just return None
        lookup_url_kwarg = self._get_lookup_field_name()
        try:
            if lookup_url_kwarg not in self.kwargs:
                self.__dict__['get_object'] = lambda: None

            return super().options(request, *args, **kwargs)
        finally:
            self.__dict__.pop('get_object', None)


@schemas.profile_schema
class Profile(CVBaseAPIView):
    serializer_class = serializers.ProfileSerializer
    queryset = serializer_class.Meta.model.objects.select_related('user')

    def get_object(self):
        # fix for retrieve the current profile for url that does not contains URL keyword argument
        self.kwargs[self.lookup_field] = get_current_profile(self.request).pk
        return super().get_object()

    def list(self, request, *args, **kwargs):
        """
            In any case, we return the profile of the current user
        """
        return self.retrieve(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        profile = get_current_profile(request, False)
        if profile:
            raise PermissionDenied('The profile already exists, use the PUT action to modify it')
        return super().post(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        raise PermissionDenied('Profile delete is forbidden, use the PUT action to modify it')


@schemas.education_schema
class Education(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.EducationSerializer
    filter_backends = [MyselfFilter]


@schemas.hobby_schema
class Hobby(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.HobbySerializer
    filter_backends = [MyselfFilter]


@schemas.language_schema
class Language(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.LanguageSerializer
    filter_backends = [MyselfFilter]


@schemas.project_schema
class Project(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.ProjectSerializer
    filter_backends = [MyselfFilter]


@schemas.workplace_schema
class Workplace(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.WorkplaceSerializer
    filter_backends = [MyselfFilter]


@schemas.userresource_schema
class UserResource(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.UserResourceSerializer
    filter_backends = [MyselfFilter]


@schemas.projecttechnology_schema
class ProjectTechnology(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.ProjectTechnologySerializer
    filter_backends = [MyselfFilter]


@schemas.workplaceresponsibility_schema
class WorkplaceResponsibility(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.WorkplaceResponsibilitySerializer
    filter_backends = [MyselfFilter]


@schemas.workplaceproject_schema
class WorkplaceProject(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.WorkplaceProjectSerializer
    filter_backends = [MyselfFilter]


@api_view(['GET'])
def api_root_view(request, app_names: Iterable, sort: bool = True):
    resolver = get_resolver()
    res = {}

    for app_name in app_names:
        # A bit simplified logic has gotten from `django.urls.base.reverse` to get URLResolver for 'cv' app_name
        app_nss = resolver.app_dict.get(app_name, [])
        assert app_nss, f'app_name {app_name} does not configured properly'

        # take default app_instance info
        ns_pattern_str, ns_resolver = resolver.namespace_dict[app_nss[0]]

        # Very simplified logic, for now
        # In particular, We assume that app_name only has patterns, not url_resolver-s
        for pattern in ns_resolver.url_patterns:
            possibility, pattern_info, defaults, converters = ns_resolver.reverse_dict.getlist(pattern.callback)[0]
            result, params = possibility[0]
            if params:
                continue

            abs_url = request.build_absolute_uri(f'/{ns_pattern_str}')+str(result)
            view_class = getattr(pattern.callback, 'cls', getattr(pattern.callback, 'view_class'))
            view = view_class(**getattr(pattern.callback, 'initkwargs', getattr(pattern.callback, 'view_initkwargs', {})))
            view.setup(request)
            if hasattr(view, 'schema'):
                schema = view.schema
                schema.method = 'get'
                descr = schema.get_description()
            else:
                # For non API endpoints (like - login, logout)
                view_doc = get_doc(view.__class__)
                action_doc = get_doc(view.get)
                descr = action_doc or view_doc

            res[abs_url] = descr

    return Response({itm[0]: itm[1] for itm in sorted(res.items(), key=lambda v: v[0])} if sort else res)

