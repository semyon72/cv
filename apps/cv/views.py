from typing import Optional

from django.db.models import Model, QuerySet
from django.http import Http404
from django.shortcuts import render

# Create your views here.

from rest_framework import generics, mixins, parsers
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import (IsAuthenticated, BasePermission, SAFE_METHODS, IsAdminUser, )

from . import serializers

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


class IsReadOnlyOrAdmin(BasePermission):
    """
    The request is authenticated as a staff user, or is a read-only request.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS or
            (request.user and request.user.is_staff)
        )


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
    permission_classes = [IsReadOnlyOrAdmin]
    serializer_class = serializers.TechnologiesSerializer
    queryset = serializers.TechnologiesSerializer.Meta.model.objects.all()


class TechnologiesRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsReadOnlyOrAdmin]
    serializer_class = serializers.TechnologiesSerializer
    queryset = serializers.TechnologiesSerializer.Meta.model.objects.all()


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

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # converting pk value into int
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs.pop(lookup_url_kwarg, None)
        if pk is not None:
            self.kwargs[lookup_url_kwarg] = int(pk)

        self._initialize_queryset()

    def get(self, request, *args, **kwargs):
        """
            We must take decision on self.args or self.kwargs, Is 'GET' request either list or retrieve?
            It should be coupled with urls definition like
            re_path('^education/(?:(?P<pk>[0-9]+)/)?$', Education.as_view(), name='education')
            where `pk` is optional part
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
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


class Education(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.EducationSerializer


class Hobby(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.HobbySerializer


class Language(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.LanguageSerializer


class Project(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.ProjectSerializer


class Workplace(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.WorkplaceSerializer


class UserResource(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.UserResourceSerializer


class ProjectTechnology(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.ProjectTechnologySerializer


class WorkplaceResponsibility(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.WorkplaceResponsibilitySerializer


class WorkplaceProject(CVBaseAPIView):
    permission_classes = [IsAuthenticatedAndMyself]
    serializer_class = serializers.WorkplaceProjectSerializer

