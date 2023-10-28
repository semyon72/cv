# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: patches.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-13 (y-m-d) 8:58 AM

import datetime
import functools
from typing import Optional, Type

from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.models import (
    Value, Case, When, F, DateField, Model, Count, Min, Max, Q
)
from django.db.models.lookups import IsNull, LessThanOrEqual, Exact

from . import db_patch
from .sql import range_intersection_sql


class SQLitePatchMixin:

    def check_sqlite(self):
        """
            If it works on connection_created then each time will new connection.
            For SQLite, we need to create user-defined function on each new connection, again and again.
            Thus, no need check at all.
        """
        return False

    def _patch_sqlite_func(self, *args, **kwargs) -> Optional[int]:
        raise NotImplementedError

    def patch_sqlite(self):
        self.db_wrapper.connection.create_function(self.name, -1, self._patch_sqlite_func, deterministic=True)


class CountRangeIntersectionPatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'range_intersection_for'

    def _patch_sqlite_func(self, pkv, bv, ev, tbname, bfname='begin', efname='end', pkname='id') -> Optional[int]:
        sql, prms = range_intersection_sql(tbname, bfname, efname, pkname)
        sql = 'SELECT count(*) FROM (%s)' % sql

        with self.db_wrapper.cursor() as cursor:
            cursor.execute(sql, prms | {'bv': bv, 'ev': ev, 'pkv': pkv})
            r = cursor.fetchone()

        return None if r is None else r[0]


class EducationDatesCrossingPatch(SQLitePatchMixin, db_patch.BasePatch):
    """
        CVEducation begin...end range intersection database function for CHECK constraint that limited into user
        Also for this check, the pk-value is mandatory due to UPDATE we will need to exclude itself row from checking
    """

    name = 'edu_dates_crossing'

    def _get_model(self) -> Type[Model]:
        from .models import CVEducation
        return CVEducation

    def _patch_sqlite_func(self, pkv, pv, bv, ev) -> Optional[int]:
        """
            pkv, pv, bv, ev - values of `pk`, `profile_id`, `begin` and `end` fields
            Stored func declaration
        """
        model = self._get_model()
        opts = model._meta
        ops: BaseDatabaseOperations = self.db_wrapper.ops

        tbset = f'''(SELECT * FROM {ops.quote_name(opts.db_table)} WHERE {ops.quote_name(opts.get_field('profile').column)}=:pv)'''

        sql, prms = range_intersection_sql(
            tbset,
            ops.quote_name(opts.get_field('begin').column),
            ops.quote_name(opts.get_field('end').column),
            ops.quote_name(opts.pk.column),
            tbname_alias=ops.quote_name('edu')
        )
        sql = 'SELECT count(*) FROM (%s)' % sql

        with self.db_wrapper.cursor() as cursor:
            cursor.execute(sql, prms | {'pkv': pkv, 'pv': pv, 'bv': bv, 'ev': ev})
            r = cursor.fetchone()

        return None if r is None else r[0]


class WorkplaceDatesCrossingPatch(EducationDatesCrossingPatch):
    """
        CVWorkplace begin...end range intersection database function for CHECK constraint that limited into user
        Also for this check, the pk-value is mandatory due to UPDATE we will need to exclude itself row from checking
    """

    name = 'wp_dates_crossing'

    def _get_model(self) -> Type[Model]:
        from .models import CVWorkplace
        return CVWorkplace


class ProjectDatesCrossingPatch(EducationDatesCrossingPatch):
    """
        CVProject begin...end range intersection database function for CHECK constraint that limited into user
        Also for this check, the pk-value is mandatory due to UPDATE we will need to exclude itself row from checking
    """

    name = 'proj_dates_crossing'

    def _get_model(self) -> Type[Model]:
        from .models import CVProject
        return CVProject


class WorkplaceRespDatesCrossingPatch(SQLitePatchMixin, db_patch.BasePatch):
    """
        WorkplaceResponsibility begin...end range intersection database function for CHECK constraint
        that limited into Workplace. Also for this check, the pk-value is mandatory due to UPDATE
        we will need to exclude itself row from checking
    """

    name = 'wpresp_dates_crossing'

    @functools.cached_property
    def patch_func_model(self):
        from .models import CVWorkplaceResponsibility
        return CVWorkplaceResponsibility

    def _patch_sqlite_func(self, wpr_id, wp_id, bv, ev) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore,
                wpr_id - WorkplaceResponsibility PK - it is used during update to skip the row that changes.
                wp_id - Workplace PK - it is used to select rows that belong to one Workplace.
                range [bv..ev] - will contain the corresponding data (values) to check for crossing the range

            It returns False if WorkplaceResponsibility does not already contain a corresponding (for Workplace) row or
            WorkplaceResponsibility[begin..end] does not cross range [bv..ev].
            Otherwise True (date crossing exists)
        """

        # If one of the rows contains the `end` that is Null, returns Null, otherwise MAX(`end`)
        # `end` == null means infinity (to the present time and further)
        # CASE WHEN MAX(CASE WHEN end IS NULL THEN 1 ELSE 0 END) = 0 THEN MAX(end) ELSE NULL END
        max_case = Case(
            When(Exact(Max(Case(When(end__isnull=True, then=Value(1)), default=Value(0))), Value(0)), Max('end')),
            default=None
        )

        res: dict = self.patch_func_model.objects.filter(~Q(pk=wpr_id), workplace=wp_id).aggregate(
            cnt=Count('*'),
            begin=Min('begin'),
            end=max_case,
        )

        # no matching rows found -> no intersection
        if res['cnt'] == 0:
            return False

        dbv = None if bv is None else datetime.date.fromisoformat(bv)
        dev = None if ev is None else datetime.date.fromisoformat(ev)
        return (res['end'] is None or dbv <= res['end']) and (dev is None or dev >= res['begin'])


class WorkplaceRespDatesInWorkplacePatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'wpresp_dates_in_wp'

    def _patch_sqlite_func(self, workpalce_id, begin, end) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, workpalce_id and range (begin + end) will contain corresponding data (values) that
            is not added in CVWorkplaceResponsibility yet

            It returns number rows (exact 1 for CVWorkplace.(begin..end) which contains (begin..end)).
            It will used in CVWorkplaceResponsibility as constraint and
            if CVWorkplaceResponsibility.(begin...end) not in CVWorkplace.(begin...end) then this is fail
        """
        from .models import CVWorkplace

        exp = Case(
            When(
                IsNull(Value(end, output_field=DateField()), True),
                then=IsNull(F('end'), True)
            ),
            default=Case(
                When(IsNull(F('end'), True), then=Value(True)),
                default=LessThanOrEqual(Value(end, output_field=DateField()), F('end'))
            )
        )
        v = CVWorkplace.objects.filter(
            exp,
            begin__lte=Value(begin, output_field=DateField()),
            pk=Value(workpalce_id)
        ).count()
        return v


class ProjectTechnologyDurationInProjectPatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'projtech_duration_in_proj'

    def _patch_sqlite_func(self, project_id, duration) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, project_id and duration will contain corresponding data (values) that
            is not added in CVProjectTechnology yet

            It returns False for CVProject.(end - begin) < duration + some check the null values.
            It will used in CVProjectTechnology as constraint and
            if CVProject.(end - begin) >= CVProjectTechnology.duration + some check the null values then True
        """
        from .models import CVProject

        rows = CVProject.objects.values('begin', 'end').filter(pk=Value(project_id))[:2]
        if len(rows) != 1:
            return None
        r: dict = rows[0]

        if r['end'] is None:
            return True

        if duration is None:
            return False

        return (r['end'] - r['begin']) // datetime.timedelta(microseconds=1) >= duration


class WorkplaceProjectSameUserPatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'wpproj_same_user'

    def _patch_sqlite_func(self, workpalce_id, project_id) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, workpalce_id and project_id will contain corresponding data (values) that
            is not added in CVWorkplaceProject yet

            It returns number rows (exact 1 for CVWorkplace.profile_id == CVProject.profile_id).
            It will used in CVWorkplaceProject as constraint and
            if CVWorkplace.profile_id != CVProject.profile_id then this is fail
        """
        from .models import CVWorkplace, CVProject

        sq_proj = CVProject.objects.filter(pk=project_id).values('profile')[:1]
        q = CVWorkplace.objects.filter(pk=workpalce_id, profile=sq_proj).values('profile')

        return q.count()


class WorkplaceProjectProjectDatesInWorkplacePatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'wpproj_proj_dates_in_wp'

    def _patch_sqlite_func(self, workpalce_id, project_id) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, workpalce_id and project_id will contain corresponding data (values) that
            is not added in CVWorkplaceProject yet

            It returns number rows (exact 1 for CVWorkplace.(end...begin) >= CVProject.(end...begin)).
            It will used in CVWorkplaceProject as constraint and
            if CVWorkplace.(end...begin) < CVProject.(end...begin) then (0) fail
        """
        from .models import CVWorkplace, CVProject
        proj_pkname = CVProject._meta.pk.attname
        wp_pkname = CVWorkplace._meta.pk.attname
        sql = f'SELECT proj.{proj_pkname} FROM {CVWorkplace._meta.db_table} as wp,' \
              f' {CVProject._meta.db_table} as proj ' \
              f'WHERE wp.{wp_pkname} = %s and proj.{proj_pkname} = %s and wp.begin <= proj.begin and ' \
              f'(wp.end is null or (proj.end is not null and wp.end >= proj.end))'

        return len(CVProject.objects.raw(sql, (workpalce_id, project_id)))


class WorkplaceDatesGTEProjectPatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'wp_dates_gte_proj'

    @functools.cached_property
    def patch_func_model(self):
        from .models import CVWorkplaceProject
        return CVWorkplaceProject

    def _patch_sqlite_func(self, workpalce_id, begin, end) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, `workpalce_id`, `begin` and `end` will contain the corresponding data (values) that
            modify or create a new CVWorkplace

            workpalce_id - is CVWorkplace.id
            begin - is CVWorkplace.begin
            end - is CVWorkplace.end

            It returns True if CVProject does not already contain corresponding row or
            CVWorkplace[begin..end] is greater than or equal to CVProject.[begin..end].
            Otherwise False
        """
        # CASE WHEN MAX(CASE WHEN end IS NULL THEN 1 ELSE 0 END) = 0 THEN MAX(end) ELSE NULL END
        max_case = Case(
            When(
                Exact(Max(Case(When(project__end__isnull=True, then=Value(1)), default=Value(0))), Value(0)),
                Max('project__end')
            ),
            default=None
        )

        # It will execute something like
        # SELECT COUNT(*) AS "cnt", MIN("cv_cvproject"."begin") AS "begin",
        # CASE WHEN MAX(CASE WHEN ("cv_cvproject"."end" IS NULL) THEN 1 ELSE 0 END) = (0) THEN MAX("cv_cvproject"."end") ELSE NULL END AS "end"
        # FROM "cv_cvworkplaceproject" INNER JOIN "cv_cvproject" ON ("cv_cvworkplaceproject"."project_id" = "cv_cvproject"."id")
        # WHERE "cv_cvworkplaceproject"."workplace_id" = 1
        pr: dict = self.patch_func_model.objects.filter(workplace=workpalce_id).aggregate(
            cnt=Count('*'),
            begin=Min('project__begin'),
            end=max_case,
        )

        if pr['cnt'] == 0:
            return True

        return datetime.date.fromisoformat(begin) <= pr['begin'] and (
                end is None or (pr['end'] is not None and datetime.date.fromisoformat(end) >= pr['end'])
        )


class WorkplaceDatesGTEWorkplaceRespPatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'wp_dates_gte_wpresp'

    @functools.cached_property
    def patch_func_model(self):
        from .models import CVWorkplaceResponsibility
        return CVWorkplaceResponsibility

    def _patch_sqlite_func(self, workpalce_id, begin, end) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, `workpalce_id`, `begin` and `end` will contain the corresponding data (values) that
            modify or create a new CVWorkplace

            workpalce_id - is CVWorkplace.id
            begin - is CVWorkplace.begin
            end - is CVWorkplace.end

            It returns True if CVWorkplaceResponsibility does not already contain corresponding row or
            CVWorkplace[begin..end] is greater than or equal to CVWorkplaceResponsibility.[begin..end].
            Otherwise False
        """
        # CASE WHEN MAX(CASE WHEN end IS NULL THEN 1 ELSE 0 END) = 0 THEN MAX(end) ELSE NULL END
        max_case = Case(
            When(
                Exact(Max(Case(When(end__isnull=True, then=Value(1)), default=Value(0))), Value(0)),
                Max('end')
            ),
            default=None
        )

        # It will execute something like .... (see WorkplaceDatesGTEProjectPatch)
        res: dict = self.patch_func_model.objects.filter(workplace=workpalce_id).aggregate(
            cnt=Count('*'),
            begin=Min('begin'),
            end=max_case,
        )

        if res['cnt'] == 0:
            return True

        return datetime.date.fromisoformat(begin) <= res['begin'] and (
                end is None or (res['end'] is not None and datetime.date.fromisoformat(end) >= res['end'])
        )


class ProjectDatesLTEWorkplacePatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'proj_dates_lte_wp'

    @functools.cached_property
    def patch_func_model(self):
        from .models import CVWorkplaceProject
        return CVWorkplaceProject

    def _patch_sqlite_func(self, project_id, begin, end) -> Optional[int]:
        """
            Same as WorkplaceDatesGTEProjectPatch but in reverse direction

            We suppose that this function will called in check constraint.
            Therefore, `project_id`, `begin` and `end` will contain the corresponding data (values) that
            modify or create a new CVProject

            project_id - is CVProject.id
            begin - is CVProject.begin
            end - is CVProject.end

            It returns True if CVWorkplace does not already contain  corresponding row or
            CVProject[begin..end] is less than or equal to CVWorkplace.[begin..end].
            Otherwise False
        """
        max_case = Case(
            When(
                Exact(Max(Case(When(workplace__end__isnull=True, then=Value(1)), default=Value(0))), Value(0)),
                Max('workplace__end')
            ),
            default=None
        )

        wpr = self.patch_func_model.objects.filter(project=project_id).aggregate(
            cnt=Count('*'),
            begin=Min('workplace__begin'),
            end=max_case,
        )

        if wpr['cnt'] == 0:
            return True

        return wpr['begin'] <= datetime.date.fromisoformat(begin) and (
                wpr['end'] is None or (end is not None and datetime.date.fromisoformat(end) <= wpr['end'])
        )


class ProjectDatesGTEProjectTechnologyPatch(SQLitePatchMixin, db_patch.BasePatch):

    name = 'proj_dates_gte_projtech'

    @functools.cached_property
    def patch_func_model(self):
        from .models import CVProjectTechnology
        return CVProjectTechnology

    def _patch_sqlite_func(self, project_id, begin, end) -> Optional[int]:
        """
            We suppose that this function will called in check constraint.
            Therefore, `project_id`, `begin` and `end` will contain the corresponding data (values) that
            modify or create a new CVProject

            project_id - is CVProject.id
            begin - is CVProject.begin
            end - is CVProject.end

            It returns True if CVProjectTechnology does not already contain corresponding row or
            CVProject[begin..end] is greater than or equal to CVProjectTechnology.duration.
            Otherwise False
        """
        # CASE WHEN MAX(CASE WHEN end IS NULL THEN 1 ELSE 0 END) = 0 THEN MAX(duration) ELSE NULL END
        max_case = Case(
            When(
                Exact(Max(Case(When(duration__isnull=True, then=Value(1)), default=Value(0))), Value(0)),
                Max('duration')
            ),
            default=None
        )

        # It will execute something, almost, like .... (see WorkplaceDatesGTEProjectPatch)
        res: dict = self.patch_func_model.objects.filter(project=project_id).aggregate(
            cnt=Count('*'),
            duration=max_case,
        )

        if res['cnt'] == 0:
            return True

        return end is None or (
                res['duration'] is not None and
                datetime.date.fromisoformat(end) - datetime.date.fromisoformat(begin) >= res['duration']
        )


class TechnologyUniqueTogetherWithProfilePatch(SQLitePatchMixin, db_patch.BasePatch):
    """
        Because the value `null` will be recognized as different in the `unique` constraint then
        we will have the duplication for
        `INSERT INTO cv_cvtechnologies (technology, profile_id) VALUES('3333333333333333', null)`
        if we run this twice

        We need to implement a function that takes `technology` and `profile_id` as parameters
        and executes the SQL that is similar to
        SELECT COUNT(*)
        FROM cv_cvtechnologies
        WHERE CASE WHEN profile_id is null THEN profile_id is 9 ELSE profile_id == 9 END
        and technology='3333333333333333'
    """

    name = 'technology_unique_together_with_profile'

    @functools.cached_property
    def patch_func_model(self):
        from .models import CVTechnologies
        return CVTechnologies

    def _patch_sqlite_func(self, technology_id, technology: str, profile_id: Optional[int]) -> bool:
        """
            We suppose that this function will called in check constraint.
            Therefore, `technology` and `profile_id` will contain the corresponding data (values) that
            modify or create a new CVTechnologies

            technology_id - is CVTechnologies.id. This value will be used to exclude itself on `update` action
            technology - is CVTechnologies.technology
            profile_id - is CVTechnologies.profile_id

            It returns True if CVTechnologies has no duplicates
        """
        if_null_case = Case(
            When(
                profile__isnull=True,
                then=Case(
                    When(IsNull(Value(profile_id), True), then=Value(True)),
                    default=Value(False)
                )
            ),
            default=Exact(F('profile'), profile_id)
        )
        qs = self.patch_func_model.objects.filter(if_null_case, ~Q(pk=technology_id), technology=technology)
        return qs.count() == 0


class CVPatcher(db_patch.Patcher):

    patches = [
        CountRangeIntersectionPatch,
        EducationDatesCrossingPatch,
        WorkplaceDatesCrossingPatch,
        ProjectDatesCrossingPatch,
        WorkplaceRespDatesCrossingPatch,
        WorkplaceRespDatesInWorkplacePatch,
        ProjectTechnologyDurationInProjectPatch,
        WorkplaceProjectSameUserPatch,
        WorkplaceProjectProjectDatesInWorkplacePatch,
        WorkplaceDatesGTEProjectPatch,
        ProjectDatesLTEWorkplacePatch,
        WorkplaceDatesGTEWorkplaceRespPatch,
        ProjectDatesGTEProjectTechnologyPatch,
        TechnologyUniqueTogetherWithProfilePatch,
    ]


cv_patcher = CVPatcher()
