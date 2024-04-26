# IDE: PyCharm
# Project: cv
# Path: apps/cv_ui
# File: urls.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2024-01-09 (y-m-d) 1:49 PM

from django.urls import path, include

from . import views


app_name = 'cv_ui'

urlpatterns = [
    path('', views.Index.as_view(), name='index'),
    # path('education/', views.Education.as_view(), name='education'),
    # path('hobby/', views.Hobby.as_view(template_name='cv_ui/hobby/list.html'), name='hobby-list'),
    # path('hobby/<str:action>/',
    #      views.Hobby.as_view(template_name='cv_ui/hobby/create.html'),
    #      kwargs={'action': 'create'}, name='hobby-create'
    #      ),
    # path('hobby/<int:pk>/', views.Hobby.as_view(template_name='cv_ui/hobby/read.html'), name='hobby-read'),
    # path('hobby/<int:pk>/update/', views.Hobby.as_view(template_name='cv_ui/hobby/update.html'), name='hobby-update'),
    *views.Hobby.get_patterns().values(),
    *views.Education.get_patterns().values(),
]
