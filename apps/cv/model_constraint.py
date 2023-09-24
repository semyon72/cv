# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: model_constraint.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-19 (y-m-d) 12:52 PM

from typing import Union, Type

from django.db import models

from django.db.models import (
    CheckConstraint, Q, F, Value, Field, BaseConstraint, IntegerField, BooleanField
)

from django.db.models.functions import Trim, Length
from django.db.models.lookups import Range, IsNull, Exact, GreaterThanOrEqual
from django.db.models.query_utils import DeferredAttribute

from apps.cv.db_functions import (
    RangeIntersectionFor, EducationDatesCrossing, WorkplaceDatesCrossing, ProjectDatesCrossing,
    WorkplaceRespDatesInWorkplace, ProjectTechnologyDurationInProject, WorkplaceProjectSameUser,
    WorkplaceProjectProjectDatesInWorkplace, WorkplaceDatesGTEProject, ProjectDatesLTEWorkplace,
    WorkplaceDatesGTEWorkplaceResp, ProjectDatesGTEProjectTechnology, WorkplaceRespDatesCrossing,
)


def create_constraint_name(field: Field, name):
    fmt_str = '%(table)s_%(field)s_%(name)s'
    prms = {
        'table': field.model._meta.db_table,
        'field': field.attname,
        'name': name
    }
    return fmt_str % prms


def length_range_constraint(field: Union[Field, DeferredAttribute]) -> BaseConstraint:
    if isinstance(field, DeferredAttribute):
        field = field.field

    qargs = []

    if not field.null:
        qargs.append(IsNull(F(field.attname), False))

    if field.max_length is not None:
        qargs.append(Range(Length(Trim(F(field.attname))), (Value(min(1, field.max_length)), Value(field.max_length))))

    if qargs:
        return CheckConstraint(
            check=Q(*qargs),
            name=create_constraint_name(field, 'range')
        )


def _date_begin_end_settings_pre_check(begin: Field, end: Field):
    if not isinstance(begin, models.DateField) or not isinstance(end, models.DateField):
        raise ValueError('`begin` and `end` must be instance of %s' % models.DateField.__name__)

    if begin.null and end.null:
        return False

    if begin.null:
        raise ValueError('`begin` should not be nullable')

    return True


def date_end_gte_begin_or_null_constraint(begin: Field, end: Field) -> BaseConstraint:
    if _date_begin_end_settings_pre_check(begin, end):
        return CheckConstraint(
            check=Q(
                IsNull(F(begin.attname), False),
                IsNull(F(end.attname), True) | GreaterThanOrEqual(F(end.attname), F(begin.attname))
            ),
            name=create_constraint_name(begin, 'end_gte_begin_or_null')
        )


def range_intersection_constraint(begin: Field, end: Field) -> BaseConstraint:
    if _date_begin_end_settings_pre_check(begin, end):
        opts = begin.model._meta
        return CheckConstraint(
            check=Exact(
                RangeIntersectionFor(
                    F(opts.pk.attname), F(begin.attname), F(end.attname),
                    Value(opts.db_table), Value(begin.column), Value(end.column), Value(opts.pk.column),
                    output_field=IntegerField()
                ),
                Value(0),
            ),
            name=create_constraint_name(begin, 'end_date_range_intersection')
        )


# Specialized constraints - for certain tables using the stored functions

def _dates_crossing_for_user_constraint(begin: Field, end: Field, *, db_func: Type, cname_sufix: str = 'end_dates_intersect') -> BaseConstraint:
    """
        These constraints are limited into `profile`.
        Other logic is equal to range_intersection_constraint
    """
    if _date_begin_end_settings_pre_check(begin, end):
        opts = begin.model._meta
        return CheckConstraint(
            check=Exact(
                db_func(
                    F(opts.pk.attname), F(opts.get_field('profile').attname), F(begin.attname), F(end.attname),
                    output_field=IntegerField()
                ),
                Value(0),
            ),
            name=create_constraint_name(begin, cname_sufix)
        )


def education_dates_crossing_constraint(begin: Field, end: Field) -> BaseConstraint:
    return _dates_crossing_for_user_constraint(begin, end, db_func=EducationDatesCrossing)


def workplace_dates_crossing_constraint(begin: Field, end: Field) -> BaseConstraint:
    return _dates_crossing_for_user_constraint(begin, end, db_func=WorkplaceDatesCrossing)


def project_dates_crossing_constraint(begin: Field, end: Field) -> BaseConstraint:
    return _dates_crossing_for_user_constraint(begin, end, db_func=ProjectDatesCrossing)


def workplace_responsibility_dates_in_workplace_constraint(workplace: Field, begin: Field, end: Field) -> BaseConstraint:
    if workplace.model.__name__ != 'CVWorkplaceResponsibility':
        raise ValueError('`workplace` field must be field of CVWorkplaceResponsibility model')

    return CheckConstraint(
        check=Exact(
            WorkplaceRespDatesInWorkplace(
                F(workplace.attname), F(begin.attname), F(end.attname),
                output_field=IntegerField()
            ),
            Value(1)
        ),
        name=create_constraint_name(workplace, 'range_in_workplace')
    )


def workplace_responsibility_dates_crossing_constraint(begin: Field, end: Field) -> BaseConstraint:
    if begin.model.__name__ != 'CVWorkplaceResponsibility':
        raise ValueError('`workplace` field must be field of CVWorkplaceResponsibility model')

    return CheckConstraint(
        check=Exact(
            WorkplaceRespDatesCrossing(
                F(begin.model._meta.pk.attname), F(begin.model._meta.get_field('workplace').attname),
                F(begin.attname), F(end.attname),
                output_field=BooleanField()
            ),
            Value(False)
        ),
        name=create_constraint_name(begin, 'end_date_range_intersection')
    )


def project_technology_duration_in_project_constraint(project: Field, duration: Field) -> BaseConstraint:
    if duration.model.__name__ != 'CVProjectTechnology':
        raise ValueError('`duration` field must be field of CVProjectTechnology model')

    return CheckConstraint(
        check=ProjectTechnologyDurationInProject(
            F(project.attname), F(duration.attname),
            output_field=BooleanField()
        ),
        name=create_constraint_name(duration, 'project_technology_check')
    )


def workplace_project_same_user_constraint(workplace: Field, project: Field) -> BaseConstraint:
    if workplace.model.__name__ != 'CVWorkplaceProject':
        raise ValueError('`workplace` field must be field of CVWorkplaceProject model')

    return CheckConstraint(
        check=Exact(
            WorkplaceProjectSameUser(
                F(workplace.attname), F(project.attname),
                output_field=IntegerField()
            ),
            Value(1)
        ),
        name=create_constraint_name(workplace, 'project_same_user')
    )


def workplace_project_project_dates_in_workplace_constraint(workplace: Field, project: Field) -> BaseConstraint:
    if workplace.model.__name__ != 'CVWorkplaceProject':
        raise ValueError('`workplace` field must be field of CVWorkplaceProject model')

    return CheckConstraint(
        check=Exact(
            WorkplaceProjectProjectDatesInWorkplace(
                F(workplace.attname), F(project.attname),
                output_field=IntegerField()
            ),
            Value(1)
        ),
        name=create_constraint_name(workplace, 'project_duration')
    )


def workplace_dates_gte_project_constraint(begin: Field, end: Field) -> BaseConstraint:
    if begin.model.__name__ != 'CVWorkplace':
        raise ValueError('`begin` field must be field of CVWorkplace model')

    return CheckConstraint(
        check=WorkplaceDatesGTEProject(
                F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname),
                output_field=BooleanField()
            ),
        name=create_constraint_name(begin, 'end_range_gte_project')
    )


def workplace_dates_gte_workplace_responsibility(begin: Field, end: Field) -> BaseConstraint:
    if begin.model.__name__ != 'CVWorkplace':
        raise ValueError('`begin` field must be field of CVWorkplace model')

    return CheckConstraint(
        check=WorkplaceDatesGTEWorkplaceResp(
                F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname),
                output_field=BooleanField()
            ),
        name=create_constraint_name(begin, 'end_range_gte_wpresp')
    )


def project_dates_lte_workplace_constraint(begin: Field, end: Field) -> BaseConstraint:
    if begin.model.__name__ != 'CVProject':
        raise ValueError('`begin` field must be field of CVProject model')

    return CheckConstraint(
        check=ProjectDatesLTEWorkplace(
                F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname),
                output_field=BooleanField()
            ),
        name=create_constraint_name(begin, 'end_range_lte_workplace')
    )


def project_dates_gte_project_technology(begin: Field, end: Field) -> BaseConstraint:
    if begin.model.__name__ != 'CVProject':
        raise ValueError('`begin` field must be field of CVProject model')

    return CheckConstraint(
        check=ProjectDatesGTEProjectTechnology(
                F(begin.model._meta.pk.attname), F(begin.attname), F(end.attname),
                output_field=BooleanField()
            ),
        name=create_constraint_name(begin, 'end_range_gte_projtech')
    )


def add_constraints(**field_names):
    """
        field_names should be dict[str, callable[Field, BaseConstraint]]
        or dict[str, tuple(callable[Field, BaseConstraint])]
        or dict[str, list(callable[Field, BaseConstraint])]
        where field_names either 'field_name' or 'field_name1__field_name2__field_nameN'
        that must be passed into callable
    """
    def wrapper(cls: Type[models.Model]):
        for f__names, callbacks in field_names.items():
            fields = tuple(cls._meta.get_field(fn) for fn in f__names.split('__'))
            if not isinstance(callbacks, (tuple, list)):
                callbacks = [callbacks]
            for cbck in callbacks:
                constr = cbck(*fields)
                if isinstance(constr, BaseConstraint):
                    cls._meta.constraints.append(constr)
        return cls

    return wrapper
