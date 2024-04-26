# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: urls.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-07-03 (y-m-d) 12:32 PM

from django.urls import path, include, re_path
# from rest_framework.schemas import get_schema_view
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from apps.cv import views

app_name = 'cv'

pk_re_pattern = r'^%s/(?:(?P<pk>[0-9]+)/)?$'

schema_url_patterns = [
    path('', views.api_root_view, kwargs={'app_names': ('cv', 'rest_framework'), 'sort': False}, name='api_root'),
    path('user/', views.UserRetrieveUpdate.as_view(), name='user'),
    re_path(pk_re_pattern % 'profile', views.Profile.as_view(), name='profile'),
    path('profile/photo/', views.ProfilePhotoUpdate.as_view(), name='profile-photo'),
    path('resource/', views.ResourcesListCreate.as_view(), name='resource-lc'),
    path('resource/<int:pk>/', views.ResourcesRetrieveUpdateDestroy.as_view(), name='resource-rud'),
    path('technology/', views.TechnologiesListCreate.as_view(), name='technology-lc'),
    path('technology/<int:pk>/', views.TechnologiesRetrieveUpdateDestroy.as_view(), name='technology-rud'),
    re_path(pk_re_pattern % 'education', views.Education.as_view(), name='education'),
    re_path(pk_re_pattern % 'hobby', views.Hobby.as_view(), name='hobby'),
    re_path(pk_re_pattern % 'language', views.Language.as_view(), name='language'),
    re_path(pk_re_pattern % 'project', views.Project.as_view(), name='project'),
    re_path(pk_re_pattern % 'workplace', views.Workplace.as_view(), name='workplace'),
    re_path(pk_re_pattern % 'user-resource', views.UserResource.as_view(), name='user-resource'),
    re_path(pk_re_pattern % 'project-technology', views.ProjectTechnology.as_view(), name='project-technology'),
    re_path(pk_re_pattern % 'workplace-responsibility', views.WorkplaceResponsibility.as_view(),
            name='workplace-responsibility'),
    re_path(pk_re_pattern % 'workplace-project', views.WorkplaceProject.as_view(), name='workplace-project'),

    # path('schema/', views.api_root_view, kwargs={'app_names': ('rest_framework',)}, name='api_root_schema'),
    path('schema/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='cv:schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='cv:schema'), name='redoc'),
]

# schema_view = get_schema_view(
#     title='Server Monitoring API',
#     description="API for all things",
#     version="1.0.0",
#     # terms_of_service="http://example.com/terms/",
#     # contact={
#     #     "name": "API Support",
#     #     "url": "http://www.example.com/support",
#     #     "email": "support@example.com"
#     # },
#     # license={
#     #     "name": "Apache 2.0",
#     #     "url": "https://www.apache.org/licenses/LICENSE-2.0.html"
#     # },
#     patterns=schema_url_patterns,
# )

urlpatterns = [
    # path('', schema_view, name='openapi-schema'),
    *schema_url_patterns,
]

