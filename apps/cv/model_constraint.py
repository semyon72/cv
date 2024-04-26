# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: model_constraint.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-19 (y-m-d) 12:52 PM
import functools
from typing import Union, Type

from django.db import models

from django.db.models import (
    CheckConstraint, Q, F, Value, Field, BaseConstraint, IntegerField, BooleanField
)

from django.db.models.functions import Trim, Length
from django.db.models.lookups import Range, IsNull, Exact, GreaterThanOrEqual
from django.db.models.query_utils import DeferredAttribute

from apps.cv.db_functions import (
    WorkplaceRespDatesInWorkplace, ProjectTechnologyDurationInProject, WorkplaceProjectSameUser,
    WorkplaceProjectProjectDatesInWorkplace, WorkplaceDatesGTEProject, ProjectDatesLTEWorkplace,
    WorkplaceDatesGTEWorkplaceResp, ProjectDatesGTEProjectTechnology, WorkplaceRespDatesCrossing,
    TechnologyUniqueTogetherWithProfile,
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
        qargs.append(
            Range(
                Length(Trim(F(field.attname))),
                (Value(min(0 if field.blank else 1, field.max_length)), Value(field.max_length))
            )
        )

    if qargs:
        return CheckConstraint(
            check=Q(*qargs),
            name=create_constraint_name(field, 'range')
        )


# Specialized constraints - for certain tables using the stored functions
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


def technology_unique_together_with_profile(technology: Field) -> BaseConstraint:
    if technology.model.__name__ != 'CVTechnologies':
        raise ValueError('`technology` field must be field of CVTechnology model')

    return CheckConstraint(
        check=TechnologyUniqueTogetherWithProfile(
            F(technology.model._meta.pk.attname),
            F(technology.attname),
            F(technology.model._meta.get_field('profile').attname),
            output_field=BooleanField()
        ),
        name=create_constraint_name(technology, 'unique_together_with_profile')
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


class BaseExpressedConstraint(CheckConstraint):

    default_name: str = None
    default_check: models.Expression = None

    def __init__(self, *, check=None, name=None, violation_error_message=None):
        if name is None:
            name = self.get_default_name()

        if check is None:
            check = self.default_check

        super().__init__(check=check, name=name, violation_error_message=violation_error_message)

    def get_default_name(self):
        return self.default_name or ''.join(functools.reduce(
            lambda chrs, chr1: chrs+['_', chr1.lower()] if chr1.isupper() else chrs+[chr1.lower()],
            type(self).__name__,
            []
        )).lstrip('_')

    def set_name_prefix(self, value) -> CheckConstraint:
        self.name = f'{value}_{self.name}'
        return self


class DateBeginIsNotNullAndEndIsGreaterOrEqualConstraint(BaseExpressedConstraint):
    default_check = Q(IsNull(F('begin'), False), IsNull(F('end'), True) | GreaterThanOrEqual(F('end'), F('begin')))

    def __init__(self, *, check=None, name=None, violation_error_message=None):
        super().__init__(check=check, name=name, violation_error_message=violation_error_message)


class DatesCrossingFunc(models.Func):
    expressions = [F('pk'), F('profile'), models.F('begin'), models.F('end'), models.F('allow_date_crossing')]

    def __init__(self, *expressions, output_field=None, **extra):

        if not expressions:
            expressions = self.expressions
            output_field = models.BooleanField()

        if self.function is None:
            self.function = type(self).__name__

        self.arity = len(expressions)
        super().__init__(*expressions, output_field=output_field, **extra)


class EducationDatesCrossingFunc(DatesCrossingFunc):
    function = __qualname__  # 'EducationDatesCrossingFunc'


class EducationDateCrossingConstraint(BaseExpressedConstraint):
    default_check = EducationDatesCrossingFunc()


class ProjectDatesCrossingFunc(DatesCrossingFunc):
    function = __qualname__  # 'ProjectDatesCrossingFunc'


class ProjectDateCrossingConstraint(EducationDateCrossingConstraint):
    default_check = ProjectDatesCrossingFunc()


class WorkplaceDatesCrossingFunc(DatesCrossingFunc):
    function = __qualname__


class WorkplaceDateCrossingConstraint(EducationDateCrossingConstraint):
    default_check = WorkplaceDatesCrossingFunc()


class WorkplaceResponsibilityDatesCrossingFunc(DatesCrossingFunc):
    function = __qualname__
    expressions = [F('pk'), F('workplace'), models.F('begin'), models.F('end')]


class WorkplaceResponsibilityDateCrossingConstraint(EducationDateCrossingConstraint):
    default_check = WorkplaceResponsibilityDatesCrossingFunc()
