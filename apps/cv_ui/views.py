import enum
import functools
import inspect
import re
from typing import Union, Optional

from django.contrib.auth.views import redirect_to_login
from django.http.response import HttpResponseRedirectBase
from django.shortcuts import render, redirect

# Create your views here.

from django.http import HttpResponse, HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.urls.resolvers import RoutePattern
from django.views.generic import View, TemplateView
from rest_framework import status
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.serializers import BaseSerializer

from ..cv import views as api_views


def hello_world(request):
    return HttpResponse('Hello World')


# class EducationTemplateHTMLRenderer(TemplateHTMLRenderer):
#     template_name = 'cv_ui/index.html'
#
#     def get_template_context(self, data, renderer_context):
#         if data is renderer_context['response'].data:
#             context = renderer_context
#             context['data'] = data
#         else:
#             context = data
#         context |= super().get_template_context({}, renderer_context)
#         return context
#
#
# class Education(api_views.Education):
#     renderer_classes = [EducationTemplateHTMLRenderer]
#
#     def dispatch(self, request, *args, **kwargs):
#         response = super().dispatch(request, *args, **kwargs)
#         if response.status_code == status.HTTP_403_FORBIDDEN:
#             response = redirect_to_login(request.build_absolute_uri())
#         return response


class CRUDAction(enum.Enum):
    LIST = 'list'
    CREATE = 'create'
    RETRIEVE = 'retrieve'
    UPDATE = 'update'
    DELETE = 'delete'


class CRUDTemplateViewSet(TemplateView):

    # default value, but if used cls.get_patterns will be auto-generated for each instance
    template_name = 'cv_ui/hobby/list.html'

    api_view_class = None  # example: api_views.Hobby

    api_method_form_field_name = '_method'

    pk_url_kwarg = 'pk'
    pk_field_name = 'id'

    template_dir = None  # example: 'cv_ui/hobby/' with trailing slash

    basename = None

    action_patterns = {
        CRUDAction.LIST: '/',
        CRUDAction.CREATE: f'/{CRUDAction.CREATE.value}/',
        CRUDAction.RETRIEVE: f'/<int:{pk_url_kwarg}>/{CRUDAction.RETRIEVE.value}/',
        CRUDAction.UPDATE: f'/<int:{pk_url_kwarg}>/{CRUDAction.UPDATE.value}/',
        CRUDAction.DELETE: f'/<int:{pk_url_kwarg}>/{CRUDAction.DELETE.value}/',
    }

    @classmethod
    def get_basename_pattern(cls, pattern) -> str:
        pattern = '/'.join([(cls.basename or cls.__name__).lower().rstrip("/"), pattern.strip("/")])
        if pattern and pattern[-1] != '/':
            pattern += '/'
        return pattern

    @classmethod
    def get_action_url_name(cls, action: CRUDAction) -> str:
        return f'{cls.__name__.lower()}-{action.value}'

    @classmethod
    @functools.lru_cache
    def get_patterns(cls, initkwargs: dict = None, kwargs: dict = None):
        initkwargs = initkwargs or {}
        kwargs = kwargs or {}

        res = {}
        for action, pattern in cls.action_patterns.items():
            pattern = cls.get_basename_pattern(pattern)
            res[action] = path(
                pattern, cls.as_view(** {'template_name': f'{cls.template_dir}{action.value}.html'} | initkwargs),
                name=cls.get_action_url_name(action),
                kwargs={'action': action.value} | kwargs
            )
        return res

    @functools.lru_cache
    def get_action_map(self):
        # TODO : pattern parameters `(self.pk_url_kwarg,) ...` can be resolved automatically via request.resolver_match and get_patterns(self.initkwargs, self.kwargs)
        #  because its lru_cached it will always return same dictionary of objects, almost always.
        map2api = {
            (CRUDAction.LIST, 'get'): ('get', ()),
            (CRUDAction.CREATE, 'get'): (None, ()),
            (CRUDAction.CREATE, 'post'): ('post', ()),
            (CRUDAction.RETRIEVE, 'get'): ('get', (self.pk_url_kwarg,)),
            (CRUDAction.DELETE, 'get'): ('get', (self.pk_url_kwarg,)),
            (CRUDAction.DELETE, 'post'): ('delete', (self.pk_url_kwarg,)),
            (CRUDAction.UPDATE, 'get'): ('get', (self.pk_url_kwarg,)),
            (CRUDAction.UPDATE, 'post'): ('put', (self.pk_url_kwarg,)),
        }
        return map2api

    def resolve_action(self) -> Optional[CRUDAction]:
        action = self.kwargs.get('action')
        # auto-calculation
        if not action:
            for a, p in self.action_patterns.items():
                if self.request.resolver_match.url_name == self.get_action_url_name(a):
                    action = a.value
                    break
        if action is not None:
            assert action in (a.value for a in CRUDAction), f'resolved action {action} not in {CRUDAction}'
            action = CRUDAction(action)

        return action

    def redirect_to(self, action: CRUDAction, api_response_data) -> HttpResponseRedirect:
        _, required_api_param_names = self.get_action_map()[(action, 'get')]

        _ser: BaseSerializer = getattr(api_response_data, 'serializer', None)
        if _ser:
            _kwargs = {k: getattr(_ser.instance, k) for k in required_api_param_names}
        else:
            _kwargs = {}
            for k in required_api_param_names:
                _k = k
                if k == self.pk_url_kwarg:
                    _k = self.pk_field_name
                _kwargs[k] = api_response_data[_k]

        view_name = f'{self.request.resolver_match.view_name.split(":")[0]}:{self.get_action_url_name(action)}'
        return HttpResponseRedirect(
            reverse(view_name, kwargs=_kwargs, current_app=self.request.resolver_match.app_name)
        )

    def _process_default(self, action, method, api_method, api_kwargs) -> HttpResponse:
        self.extra_context = self.extra_context or {}
        response = None
        if api_method:
            # regular part
            if self.request.method.lower() != api_method:
                self.request.method = api_method.upper()

            kwargs = {k: v for k, v in self.kwargs.items() if k in api_kwargs}
            response = self.api_view_class.as_view()(self.request, *self.args, **kwargs)
            self.extra_context.update({'data': response.data, 'api_response': response})
        else:
            # no need make request to the API ((create, get) for example)
            self.extra_context['serializer'] = self.api_view_class().get_serializer_class()()

        return response

    def process_retrieve_get(self, action, method, api_method, api_kwargs) -> HttpResponse:
        return self._process_default(action, method, api_method, api_kwargs)

    def process_list_get(self, action, method, api_method, api_kwargs) -> HttpResponse:
        return self._process_default(action, method, api_method, api_kwargs)

    def process_update_get(self, action, method, api_method, api_kwargs):
        return self._process_default(action, method, api_method, api_kwargs)

    def process_update_post(self, action, method, api_method, api_kwargs) -> HttpResponse:
        return self._process_default(action, method, api_method, api_kwargs)

    def process_delete_get(self, action, method, api_method, api_kwargs):
        return self._process_default(action, method, api_method, api_kwargs)

    def process_delete_post(self, action, method, api_method, api_kwargs) -> HttpResponse:
        response = self._process_default(action, method, api_method, api_kwargs)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            response = self.redirect_to(CRUDAction.LIST, {})

        return response

    def process_create_get(self, action, method, api_method, api_kwargs) -> HttpResponse:
        # TODO: Think about redirect to login for users that is not Authenticated
        return self._process_default(action, method, api_method, api_kwargs)

    def process_create_post(self, action, method, api_method, api_kwargs) -> HttpResponse:
        response = self._process_default(action, method, api_method, api_kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            response = self.redirect_to(CRUDAction.RETRIEVE, dict(response.data))
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            # error
            ...
        else:
            ...

        return response

    def get(self, request, *args, **kwargs):
        action = self.resolve_action()
        method = self.request.method.lower()
        api_method, api_kwargs = self.get_action_map().get((action, method), ('get', []))
        api_method = self.request.POST.get(self.api_method_form_field_name, api_method)

        proc_func_name = f'process_{action.value}_{method}'
        proc_func = getattr(self, proc_func_name, None)
        if not proc_func:
            raise AttributeError(f'Method `{type(self).__name__}.{proc_func_name}` not found.')

        api_response = proc_func(action, method, api_method, api_kwargs)
        if api_response:
            if api_response.status_code == status.HTTP_403_FORBIDDEN:
                return redirect_to_login(request.build_absolute_uri())
            elif isinstance(api_response, HttpResponseRedirectBase):
                return api_response

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class Hobby(CRUDTemplateViewSet):
    template_name = 'cv_ui/hobby/list.html'
    api_view_class = api_views.Hobby
    template_dir = 'cv_ui/hobby/'


class Education(CRUDTemplateViewSet):
    template_name = 'cv_ui/education/list.html'
    api_view_class = api_views.Education
    template_dir = 'cv_ui/education/'



class Index(TemplateView):
    template_name = 'cv_ui/index.html'





