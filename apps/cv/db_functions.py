# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: db_functions.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-15 (y-m-d) 7:39 AM


from .patches import (
    CountRangeIntersectionPatch, EducationDatesCrossingPatch, WorkplaceDatesCrossingPatch, ProjectDatesCrossingPatch,
    WorkplaceRespDatesInWorkplacePatch, ProjectTechnologyDurationInProjectPatch, WorkplaceProjectSameUserPatch,
    WorkplaceProjectProjectDatesInWorkplacePatch, WorkplaceDatesGTEProjectPatch, ProjectDatesLTEWorkplacePatch,
    WorkplaceDatesGTEWorkplaceRespPatch, ProjectDatesGTEProjectTechnologyPatch, WorkplaceRespDatesCrossingPatch,
)

from django.db.models import Func


class RangeIntersectionFor(Func):
    """
        Accepts `expressions` with 7 elements
        [F(opts.pk.attname), F(begin.attname), F(end.attname),
         Value(opts.db_table), Value(begin.column), Value(end.column), Value(opts.pk.column)]

        look at model_constrains.range_intersection_constraint
    """
    function = CountRangeIntersectionPatch.name
    arity = 7


class EducationDatesCrossing(Func):
    """
        Accepts `expressions` with 4 elements
        pkv, uv, bv, ev - values of `pk`, `user_id`, `begin` and `end` fields

        [F(opts.pk.attname), F(user.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.education_dates_crossing_constraint
    """
    function = EducationDatesCrossingPatch.name
    arity = 4


class WorkplaceDatesCrossing(Func):
    """
        Accepts `expressions` with 4 elements
        pkv, uv, bv, ev - values of `pk`, `user_id`, `begin` and `end` fields

        [F(opts.pk.attname), F(user.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.workplace_dates_crossing_constraint
    """
    function = WorkplaceDatesCrossingPatch.name
    arity = 4


class ProjectDatesCrossing(Func):
    """
        Accepts `expressions` with 4 elements
        pkv, uv, bv, ev - values of `pk`, `user_id`, `begin` and `end` fields

        [F(opts.pk.attname), F(user.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.project_dates_crossing_constraint
    """
    function = ProjectDatesCrossingPatch.name
    arity = 4


class WorkplaceRespDatesInWorkplace(Func):
    """
        Accepts `expressions` with 3 elements
        wpv, bv, ev - values of `workplace_id`, `begin` and `end` fields

        [F(workplace.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.workplace_responsibility_dates_in_workplace_constraint
    """
    function = WorkplaceRespDatesInWorkplacePatch.name
    arity = 3


class WorkplaceRespDatesCrossing(Func):
    """
        Accepts `expressions` with 4 elements
        wpr_id, wp_id, bv, ev - values of `pk`, `workplace_id`, `begin` and `end` fields

        [F(begin.model._meta.pk.attname), F(workplace.attname), F(begin.attname), F(end.attname)]
        look at model_constrains.workplace_responsibility_dates_crossing_constraint
    """
    function = WorkplaceRespDatesCrossingPatch.name
    arity = 4


class ProjectTechnologyDurationInProject(Func):
    """
        Accepts `expressions` with 2 elements
        [F(project.attname), F(duration.attname)]

        first element is project_id field name from CVProjectTechnology,
        second is duration field name also from CVProjectTechnology

        look at model_constrains.project_technology_duration_in_project_constraint
    """
    function = ProjectTechnologyDurationInProjectPatch.name
    arity = 2


class WorkplaceProjectSameUser(Func):
    """
        Accepts `expressions` with 2 elements
        [F(workplace.attname), F(project.attname)]

        first element is `workplace_id` field name from CVWorkplaceProject,
        second is `project_id` field name also from CVWorkplaceProject

        look at model_constrains.workplace_project_same_user_constraint
    """
    function = WorkplaceProjectSameUserPatch.name
    arity = 2


class WorkplaceProjectProjectDatesInWorkplace(Func):
    """
        Accepts `expressions` with 2 elements
        [F(workplace.attname), F(project.attname)]

        first element is `workplace_id` field name from CVWorkplaceProject,
        second is `project_id` field name also from CVWorkplaceProject

        look at model_constrains.workplace_project_project_dates_in_workplace_constraint
    """
    function = WorkplaceProjectProjectDatesInWorkplacePatch.name
    arity = 2


class WorkplaceDatesGTEProject(Func):
    """
        Accepts `expressions` with 3 elements
        [F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.workplace_dates_gte_project
    """
    function = WorkplaceDatesGTEProjectPatch.name
    arity = 3


class WorkplaceDatesGTEWorkplaceResp(Func):
    """
        Accepts `expressions` with 3 elements
        [F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.workplace_dates_gte_workplace_responsibility
    """
    function = WorkplaceDatesGTEWorkplaceRespPatch.name
    arity = 3


class ProjectDatesLTEWorkplace(Func):
    """
        Accepts `expressions` with 3 elements
        [F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.project_dates_lte_workplace
    """
    function = ProjectDatesLTEWorkplacePatch.name
    arity = 3


class ProjectDatesGTEProjectTechnology(Func):
    """
        Accepts `expressions` with 3 elements
        [F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname)]

        look at model_constrains.project_dates_gte_project_technology
    """
    function = ProjectDatesGTEProjectTechnologyPatch.name
    arity = 3
