# IDE: PyCharm
# Project: cv
# Path: ${DIR_PATH}
# File: ${FILE_NAME}
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-05-16 (y-m-d) 5:18 AM
import datetime
from typing import Type

from django.db import connections

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Field, Model
from django.db.transaction import atomic
from django.test import TestCase
from apps.cv import models as cv_models
from apps.cv.models import CVTechnologies


def _test_default_begin_for_today(test_case: TestCase, model: Type[Model], **kwargs):
    # check success - default begin for today
    _kwargs = dict(kwargs)
    _kwargs.pop('begin')
    o = model.objects.create(**_kwargs)
    test_case.assertIsNotNone(o.pk)
    test_case.assertEqual(datetime.date.today(), o.begin)
    o.delete()


def _test_begin_is_none_constraint(test_case: TestCase, model: Type[Model], **kwargs):
    # check begin is None constraint
    kwargs['begin'] = None
    with test_case.assertRaises(IntegrityError) as exc:
        with atomic():
            model.objects.create(**kwargs)
    test_case.assertTrue(str(exc.exception).startswith('NOT NULL constraint failed:'))


def _multitest_by_date_data_cases(test_case: TestCase, model: Type[Model], data, **kwargs):

    for item in data:
        bv, ev = item['begin'], item['end']

        is_valid = item.pop('valid')
        if is_valid:
            caption = {'create_valid': str(bv) + '...' + str(ev)}
            with test_case.subTest(**caption):
                o = model.objects.create(** kwargs | item)
                test_case.assertIsNotNone(o.pk)
                o.delete()
        else:
            caption = {'create_invalid': str(bv) + '...' + str(ev)}
            with test_case.subTest(**caption):
                with test_case.assertRaises(IntegrityError) as exc:
                    with atomic():
                        model.objects.create(** kwargs | item)
                test_case.assertTrue(
                    str(exc.exception).startswith('CHECK constraint failed:') or
                    str(exc.exception).startswith('NOT NULL constraint failed:')
                )
        # return item's 'valid' value
        item['valid'] = is_valid


def _test_date_end_gte_begin_or_null(test_case: TestCase, model: Type[Model], **kwargs):
    data = [
        {'begin': '2023-05-05', 'end': '2023-05-10', 'valid': True},
        {'begin': '2023-05-15', 'end': None, 'valid': True},
        #
        {'begin': '2023-05-10', 'end': '2023-05-05', 'valid': False},
        {'begin': None, 'end': '2023-05-05', 'valid': False},
        {'begin': None, 'end': None, 'valid': False}
    ]

    _multitest_by_date_data_cases(test_case, model, data, **kwargs)


def _test_date_intersection_constraint(test_case: TestCase, model: Type[Model], **kwargs):

    # DATA FOR INTERSECTION TESTS
    # Source data
    intersection_tests_data = [
        {'begin': '2023-05-05', 'end': '2023-05-10'},
        {'begin': '2023-05-15', 'end': None},
    ]

    # Test cases
    intersection_tests_cases = [
        {'begin': '2023-05-03', 'end': '2023-05-07', 'valid': False},
        {'begin': '2023-05-05', 'end': '2023-05-10', 'valid': False},
        {'begin': '2023-05-03', 'end': '2023-05-11', 'valid': False},
        {'begin': '2023-05-07', 'end': '2023-05-11', 'valid': False},
        {'begin': '2023-05-13', 'end': '2023-05-16', 'valid': False},
        {'begin': '2023-05-16', 'end': '2023-05-20', 'valid': False},
        {'begin': '2023-05-03', 'end': None, 'valid': False},
        {'begin': '2023-05-09', 'end': None, 'valid': False},
        {'begin': '2023-05-10', 'end': None, 'valid': False},
        {'begin': '2023-05-13', 'end': None, 'valid': False},
        {'begin': '2023-05-15', 'end': None, 'valid': False},
        {'begin': '2023-05-17', 'end': None, 'valid': False},
        {'begin': '2023-05-01', 'end': '2023-05-05', 'valid': True},
        {'begin': '2023-05-10', 'end': '2023-05-13', 'valid': True},
        {'begin': '2023-05-10', 'end': '2023-05-15', 'valid': True},
    ]

    for item in intersection_tests_data:
        with test_case.subTest(test_data_create=str(item['begin'])+'...'+str(item['end'])):
            o = model.objects.create(** kwargs | item)
            test_case.assertIsNotNone(o.pk)

    _multitest_by_date_data_cases(test_case, model, intersection_tests_cases, **kwargs)

    # clearing
    model.objects.all().delete()


class TestCVProjects(TestCase):

    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user('test', email='test@email.lan', password='12345678')

    def test_00_cvuserprofile(self):
        """
            birthday = models.DateField(null=True, blank=True, default=None)
            photo = models.ImageField(null=True, blank=True)
        """
        o = cv_models.CVUserProfile.objects.create(user=self.user)
        self.assertIsNotNone(o.pk)
        o.delete()

        o = cv_models.CVUserProfile.objects.create(
            user=self.user, birthday=datetime.date.today(), photo='ttt.png'
        )
        self.assertIsNotNone(o.pk)

    def _get_good_text_val_for(self, field: Field):
        res = None
        if field.max_length is not None:
            res = '#' * field.max_length
        return res

    def _get_bad_text_val_for(self, field: Field):
        return '#' * (field.max_length + 1)

    def _test_text_constraint_for(self, model: Type[Model], field_name: str, **kwargs):
        field: Field = model._meta.get_field(field_name)
        kwargs[field_name] = self._get_bad_text_val_for(field)
        with self.assertRaises(IntegrityError) as exc:
            with atomic():
                model.objects.create(**kwargs)
        self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

    def _test_check_success_for(self, model: Type[Model], field_name: str, **kwargs) -> Model:
        field: Field = model._meta.get_field(field_name)
        kwargs[field_name] = self._get_good_text_val_for(field)
        o = model.objects.create(**kwargs)
        self.assertIsNotNone(o.pk)
        return o

    def test_01_cvresources(self):
        """
            Dictionary of available resources for all users, such as:
            'email' - contact, default login email
            'skipe', 'site', 'linkedin', 'telegram', ....

            resource = models.CharField(max_length=24, unique=True)
        """
        self._test_text_constraint_for(cv_models.CVResources, 'resource')
        self._test_check_success_for(cv_models.CVResources, 'resource')

        # test unique constraint
        with self.assertRaises(IntegrityError) as exc:
            with atomic():
                self._test_check_success_for(cv_models.CVResources, 'resource')
        self.assertTrue(str(exc.exception).startswith('UNIQUE constraint failed:'))

    def test_02_cvuserresource(self):
        """
            Resources are associated with the user (profile)
            Each user can have 'GitHub', 'telephone' etc

            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            resource = models.ForeignKey(CVResources, on_delete=models.CASCADE)
        """

        self._test_check_success_for(cv_models.CVResources, 'resource')
        kwargs = {
            'resource': cv_models.CVResources.objects.all()[0],
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
        }
        o = cv_models.CVUserResource.objects.create(**kwargs)
        self.assertIsNotNone(o.pk)

    def test_03_cveducation(self):
        """
            Information on user education

            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            begin = models.DateField(auto_now_add=True)
            end = models.DateField(null=True, default=None, blank=True)
            institution = models.CharField(max_length=248)
            speciality = models.CharField(max_length=248)
            degree = models.CharField(max_length=24)
            complete = models.BooleanField(default=True)
        """

        kwargs = {
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
            'begin': datetime.date.today(),
            'end': None,
            'institution': 'fgdfg',
            'speciality': 'kllk',
            'degree': 'kjlk',
            'complete': False,
        }
        model = cv_models.CVEducation

        # check 'institution' constraint
        self._test_text_constraint_for(model, 'institution', **kwargs)
        # check 'speciality' constraint
        self._test_text_constraint_for(model, 'speciality', **kwargs)
        # check 'degree' constraint
        self._test_text_constraint_for(model, 'degree', **kwargs)

        # check 'institution' success
        self._test_check_success_for(model, 'institution', **kwargs).delete()
        # check 'speciality' success
        self._test_check_success_for(model, 'speciality', **kwargs).delete()
        # check 'degree' success
        self._test_check_success_for(model, 'degree', **kwargs).delete()

        _test_date_end_gte_begin_or_null(self, model, **kwargs)
        _test_date_intersection_constraint(self, model, **kwargs)

        # check success - default begin for today
        _test_default_begin_for_today(self, model, **kwargs)

        # check begin is None constraint
        _test_begin_is_none_constraint(self, model, **kwargs)

    def test_04_cvlanguage(self):
        """
            Information about languages and proficiency level

            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            lang = models.CharField(max_length=24)
            level = models.CharField(max_length=24)
            notes = models.CharField(max_length=248)
        """
        kwargs = {
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
            'lang': 'fgdfg',
            'level': 'kllk',
            'notes': 'kjlk',
        }
        model = cv_models.CVLanguage

        # check constraints
        self._test_text_constraint_for(model, 'lang', **kwargs)
        self._test_text_constraint_for(model, 'level', **kwargs)
        self._test_text_constraint_for(model, 'notes', **kwargs)

        # check success
        self._test_check_success_for(model, 'lang', **kwargs).delete()
        self._test_check_success_for(model, 'level', **kwargs).delete()
        self._test_check_success_for(model, 'notes', **kwargs).delete()

    def test_05_cvhobby(self):
        """
            Information about hobbies
            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            description = models.TextField(null=True, blank=True)
        """
        kwargs = {
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
            'description': None,
        }
        model = cv_models.CVHobby

        # check success
        self._test_check_success_for(model, 'description', **kwargs).delete()

        kwargs['description'] = '#'*250
        o = model.objects.create(**kwargs)
        self.assertIsNotNone(o.pk)
        o.delete()

    def test_06_cvproject(self):
        """
            Projects in which the user participated.
            `begin` - required.
            if `end` is null that means infinity (current time)
            `end` can be null only for most recent project.
            `begin` and `end` are not mandatory to calculate default CVProjectTechnology.duration but helpful

            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            description = models.CharField(max_length=248)
            prerequisite = models.CharField(max_length=248)
            result = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
        """

        kwargs = {
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
            'title': 'some title',
            'description': 'fgdfg',
            'prerequisite': 'kllk',
            'result': 'kjlk',
            'begin': datetime.date.today(),
            'end': None,
        }

        model = cv_models.CVProject

        # check constraint
        self._test_text_constraint_for(model, 'title', **kwargs)
        self._test_text_constraint_for(model, 'description', **kwargs)
        self._test_text_constraint_for(model, 'prerequisite', **kwargs)
        self._test_text_constraint_for(model, 'result', **kwargs)

        # check success
        self._test_check_success_for(model, 'title', **kwargs).delete()
        self._test_check_success_for(model, 'description', **kwargs).delete()
        self._test_check_success_for(model, 'prerequisite', **kwargs).delete()
        self._test_check_success_for(model, 'result', **kwargs).delete()

        _test_date_end_gte_begin_or_null(self, model, **kwargs)
        _test_date_intersection_constraint(self, model, **kwargs)

        # check success - default begin for today
        _test_default_begin_for_today(self, model, **kwargs)

        # check begin is None constraint
        _test_begin_is_none_constraint(self, model, **kwargs)

        # TODO: add or check the test constraint for description field due to change Char to Text(max_length=8*1024)

    def test_07_cvtechnologies(self):
        """
            Dictionary like (for all users):
            'Python', 'SQL', 'Oracle' etc

            technology = models.CharField(max_length=24, unique=True)
        """
        kwargs = {}
        model = cv_models.CVTechnologies
        # check constraint
        self._test_text_constraint_for(model, 'technology', **kwargs)
        # check success
        self._test_check_success_for(model, 'technology', **kwargs).delete()

    def test_08_cvprojecttechnology(self):
        """
            Technologies that were used (+duration and notes) in a certain project

            project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
            technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
            duration = models.DurationField()
            notes = models.CharField(max_length=248)
        """
        proj_begin, proj_end = datetime.date(2023, 5, 15), datetime.date.today()
        project = cv_models.CVProject.objects.create(
            profile=cv_models.CVUserProfile.objects.create(user=self.user),
            title='tttttt', description='fgdfg', prerequisite='kllk', result='kjlk',
            begin=proj_begin, end=proj_end
        )

        kwargs = {
            'project': project,
            'technology': cv_models.CVTechnologies.objects.create(technology='fgdfg'),
            'notes': 'kllk',
            'duration': proj_end - proj_begin,
        }

        model = cv_models.CVProjectTechnology

        # check constraint
        self._test_text_constraint_for(model, 'notes', **kwargs)

        # check success
        self._test_check_success_for(model, 'notes', **kwargs).delete()

        # duration can't be more then duration of parent project
        with self.assertRaises(IntegrityError) as exc:
            with atomic():
                model.objects.create(** kwargs | {'duration': kwargs['duration'] + datetime.timedelta(1)})
        self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        # duration can't be null if parent is not null
        with self.assertRaises(IntegrityError) as exc:
            with atomic():
                model.objects.create(** kwargs | {'duration': None})
        self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        # for each Project the Technology must be unique
        o = model.objects.create(**kwargs)
        self.assertIsNotNone(o.pk)
        with self.assertRaises(IntegrityError) as exc:
            with atomic():
                model.objects.create(**kwargs)
        self.assertTrue(str(exc.exception).startswith('UNIQUE constraint failed:'))

    def test_09_cvworkplace(self):
        """
            Place where user worked

            profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
            workplace = models.CharField(max_length=248)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
        """

        begin = datetime.date(2023, 5, 15)
        end = datetime.date.today()
        kwargs = {
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
            'workplace': 'fgdfg',
            'begin': begin,
            'end': end,
        }

        model = cv_models.CVWorkplace

        # check constraint
        self._test_text_constraint_for(model, 'workplace', **kwargs)

        # check success
        self._test_check_success_for(model, 'workplace', **kwargs).delete()

        _test_date_end_gte_begin_or_null(self, model, **kwargs)
        _test_date_intersection_constraint(self, model, **kwargs)

        # check success - default begin for today
        _test_default_begin_for_today(self, model, **kwargs)

        # check begin is None constraint
        _test_begin_is_none_constraint(self, model, **kwargs)

    def test_10_cvworkplaceresponsibility(self):
        """
            Duties (responsibilities) of the user in the place where he worked.
            And role type, for example: Python Engineer, DBA and so on.

            workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
            responsibility = models.TextField()
            role = models.CharField(max_length=48)
            begin = models.DateField(default=datetime.date.today)
            end = models.DateField(null=True, default=None, blank=True)
        """

        # !!! begin - should be less than minimal date in _test_date_intersection_constraint
        # and _test_date_end_gte_begin_or_null tests
        begin = datetime.date(2023, 4, 23)
        # !!! end should be None due to
        # constraint cv_cvworkplaceresponsibility_workplace_id_responsibility_range_in_workplace
        # check (workplace_responsibility_range_in_workplace("workplace_id", "begin", "end") = (1))
        # will block standard _test_date_intersection_constraint and _test_date_end_gte_begin_or_null tests
        end = None
        wp_kwargs = {
            'profile': cv_models.CVUserProfile.objects.create(user=self.user),
            'workplace': 'fgdfg',
            'begin': begin,
            'end': end,
        }
        workplace = cv_models.CVWorkplace.objects.create(**wp_kwargs)
        kwargs = {
            'workplace': workplace,
            'responsibility': 'gsfg',
            'role': 'fgsfgs',
            'begin': begin,
            'end': end,
        }

        model = cv_models.CVWorkplaceResponsibility

        # check constraint
        self._test_text_constraint_for(model, 'role', **kwargs)
        # check success
        self._test_check_success_for(model, 'role', **kwargs).delete()

        # check 'responsibility' success is done on previous step (has some values)
        # need the test for null value constraint
        with self.assertRaises(IntegrityError) as exc:
            with atomic():
                model.objects.create(** kwargs | {'responsibility': None})
        self.assertTrue(str(exc.exception).startswith('NOT NULL constraint failed:'))

        _test_date_end_gte_begin_or_null(self, model, **kwargs)

        # check success - default begin for today
        _test_default_begin_for_today(self, model, **kwargs)

        # check begin is None constraint
        _test_begin_is_none_constraint(self, model, **kwargs)

        # main tests for CVWorkplaceResponsibility in CVWorkplace by date's range
        # !!! It should be inside cvworkplace also
        # workplace end still null, will test for this case

        data = [
            {'begin': begin - datetime.timedelta(1), 'end': None, 'valid': False},
            {'begin': None, 'end': None, 'valid': False},
            {'begin': None, 'end': begin + datetime.timedelta(10), 'valid': False},
            {'begin': begin - datetime.timedelta(1), 'end': begin + datetime.timedelta(10), 'valid': False},
            #
            {'begin': begin, 'end': begin + datetime.timedelta(10), 'valid': True},
            {'begin': begin + datetime.timedelta(1), 'end': begin + datetime.timedelta(10), 'valid': True},
            {'begin': begin, 'end': None, 'valid': True},
        ]

        _multitest_by_date_data_cases(self, model, data, **kwargs)

        # test for range where begin and end are certain dates
        workplace.end = workplace.begin + datetime.timedelta(10)
        # next line also tests - exclusion from testing the intersection for row
        # when it updates the date range with a changed date range that intersected with old values
        workplace.save()
        begin, end = workplace.begin, workplace.end

        data = [
            {'begin': begin, 'end': end, 'valid': True},
            {'begin': begin + datetime.timedelta(1), 'end': end, 'valid': True},
            {'begin': begin + datetime.timedelta(1), 'end': end - datetime.timedelta(1), 'valid': True},
            #
            {'begin': begin, 'end': None, 'valid': False},
            {'begin': begin - datetime.timedelta(1), 'end': None, 'valid': False},
            {'begin': begin + (end - begin) + datetime.timedelta(1), 'end': end + datetime.timedelta(3), 'valid': False},
            {'begin': None, 'end': None, 'valid': False},
            {'begin': begin + datetime.timedelta(1), 'end': None, 'valid': False},
            {'begin': begin - datetime.timedelta(1), 'end': end, 'valid': False},
            {'begin': begin, 'end': end + datetime.timedelta(1), 'valid': False},
            {'begin': begin - datetime.timedelta(1), 'end': end + datetime.timedelta(1), 'valid': False},
        ]

        _multitest_by_date_data_cases(self, model, data, **kwargs)

        # test for date crossing
        # workplace `end` still fixed, will test for this case
        wpr = model.objects.create(**kwargs | {
            'begin': begin + datetime.timedelta(1), 'end': begin + datetime.timedelta(4)
        })
        # wpr is inside the range of workplace and has 4 days duration [2023-04-24 .. 2023-04-27]
        data = [
            {'begin': wpr.end + datetime.timedelta(1), 'end': wpr.end + datetime.timedelta(4), 'valid': True},
            {'begin': wpr.begin - datetime.timedelta(1), 'end': wpr.begin - datetime.timedelta(1), 'valid': True},
            #
            {'begin': wpr.end, 'end': wpr.end + datetime.timedelta(3), 'valid': False},
            {'begin': wpr.end - datetime.timedelta(1), 'end': wpr.end + datetime.timedelta(3), 'valid': False},
            {'begin': wpr.begin, 'end': wpr.begin + datetime.timedelta(1), 'valid': False},
            {'begin': wpr.begin - datetime.timedelta(1), 'end': wpr.begin + datetime.timedelta(1), 'valid': False},
            {'begin': wpr.begin - datetime.timedelta(1), 'end': wpr.end + datetime.timedelta(1), 'valid': False},
            {'begin': wpr.begin - datetime.timedelta(1), 'end': None, 'valid': False},
            {'begin': wpr.begin, 'end': wpr.end, 'valid': False},
        ]

        _multitest_by_date_data_cases(self, model, data, **kwargs)

        # prepare for workplace.end-less testing
        workplace.end = None
        workplace.save()
        wpr.end = None
        wpr.save()

        data = [
            {'begin': wpr.begin - datetime.timedelta(1), 'end': wpr.begin - datetime.timedelta(1), 'valid': True},
            #
            {'begin': wpr.begin, 'end': wpr.begin + datetime.timedelta(4), 'valid': False},
            {'begin': wpr.begin, 'end': None, 'valid': False},
            {'begin': wpr.begin - datetime.timedelta(1), 'end': None, 'valid': False},
            {'begin': wpr.begin, 'end': wpr.end, 'valid': False},
        ]

        _multitest_by_date_data_cases(self, model, data, **kwargs)

    def test_11_cvworkplaceproject(self):

        begin = datetime.date(2023, 4, 23)
        end = begin + datetime.timedelta(10)
        cv_profile = cv_models.CVUserProfile.objects.create(user=self.user)

        wp_kwargs = {'profile': cv_profile, 'workplace': 'fgdfg', 'begin': begin, 'end': end}
        workplace = cv_models.CVWorkplace.objects.create(**wp_kwargs)

        proj_kwargs = {# cv_models.CVProject._meta.pk.attname: 5,
            'profile': cv_profile, 'title': 'tttttt', 'description': 'fgdfg', 'prerequisite': 'dfgdfg',
            'result': 'fgsfdgsf', 'begin': begin, 'end': end,
        }
        dummy_project = cv_models.CVProject.objects.create(** proj_kwargs | {'end': begin + datetime.timedelta(2)})

        # to understand the right id-s (like wp.id = 1, proj.id=2)
        project = cv_models.CVProject.objects.create(
            ** proj_kwargs | {'begin': dummy_project.end, 'end': dummy_project.end + datetime.timedelta(2)}
        )

        wp_proj_kwargs = {
            'workplace': workplace,
            'project': project,
        }

        # Workplace and Project have same user (profile)
        with self.subTest('right values - same user'):
            wp_proj = cv_models.CVWorkplaceProject.objects.create(**wp_proj_kwargs)
            self.assertIsNotNone(wp_proj.pk)

        # User of workplace is not same as in the project
        # CHECK constraint failed: cv_cvworkplaceproject_workplace_id_project_same_user
        user_1 = get_user_model().objects.create_user('test_1', email='test_1@email.lan', password='12345678')
        cv_profile_1 = cv_models.CVUserProfile.objects.create(user=user_1)
        project_1 = cv_models.CVProject.objects.create(
            ** proj_kwargs | {'profile': cv_profile_1, 'begin': project.end, 'end': project.end + datetime.timedelta(2)}
        )
        with self.subTest('bad values - users are differ'):
            with self.assertRaises(IntegrityError) as exc:
                with atomic():
                    cv_models.CVWorkplaceProject.objects.create(** wp_proj_kwargs | {'project': project_1})
            # CHECK constraint failed: cv_cvworkplaceproject_workplace_id_project_same_user
            self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        # workplace_project_duration_constraint
        # It should test project's begin...end inside workplace's begin...end

        # Project out of range of workplace with fixed dates
        cases = {
            '1. project is bigger than workplace (`end` is fixed)': {'end': end + datetime.timedelta(1)},
            '2. project is bigger than workplace (`begin` is less)': {'begin': begin - datetime.timedelta(1)},
            '3. project is bigger than workplace (`end` is null)': {'end': None}
        }
        wp_proj.delete()
        dummy_project.delete()
        for cname, cprms in cases.items():
            for attr, val in cprms.items():
                setattr(project, attr, val)
            project.save()
            with self.subTest(f'bad values - {cname}'):
                with self.assertRaises(IntegrityError) as exc:
                    with atomic():
                        wp_proj.save()
                # CHECK constraint failed: cv_cvworkplaceproject_workplace_id_project_duration
                self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        # Success
        cname = '1. workplace is bigger than project (`end` is null)'
        project.begin = dummy_project.end
        project.end = dummy_project.end + datetime.timedelta(2)
        project.save()
        with self.subTest(f'success - {cname}'):
            workplace.end = None
            workplace.save()
            self.assertIsNotNone(project.end)
            self.assertIsNone(wp_proj.pk)
            wp_proj.save()

        cname = '2. workplace is equal to project (both `end` are null)'
        if wp_proj.pk is not None:
            wp_proj.delete()
        project.refresh_from_db()
        with self.subTest(f'success - {cname}'):
            project.end = None
            project.save()
            self.assertIsNone(project.end)
            self.assertEqual(project.end, workplace.end)
            self.assertIsNone(wp_proj.pk)
            wp_proj.save()

    def test_12_cvworkplace_project_composite(self):
        """
            Composite test, mainly, for modification dates ranges
            model_constraint.workplace_dates_gte_project_constraint, model_constraint.project_dates_lte_workplace_constraint
        """
        today = datetime.date.today()
        wpdur = datetime.timedelta(21)
        wpb = today - wpdur // 3 * 2
        wpe = today + wpdur // 3
        self.assertEqual(wpdur, wpe - wpb)

        cv_profile = cv_models.CVUserProfile.objects.create(user=self.user)
        wp_kwargs = {'profile': cv_profile, 'workplace': 'fgdfg', 'begin': wpb, 'end': wpe}
        workplace = cv_models.CVWorkplace.objects.create(**wp_kwargs)

        proj_kwargs = {'profile': cv_profile, 'title': 'ttttt', 'description': 'fgdfg', 'prerequisite': 'dfgdfg',
                       'result': 'fgsfdgsf', 'begin': wpb, 'end': wpe}

        dummy_project = cv_models.CVProject.objects.create(** proj_kwargs | {'end': wpb + datetime.timedelta(2)})
        dummy_project.delete()
        # to understand the right id-s (like wp.id = 1, proj.id=2)
        project = cv_models.CVProject.objects.create(
            ** proj_kwargs | {'begin': dummy_project.end, 'end': dummy_project.end + datetime.timedelta(7)}
        )

        wp_proj = cv_models.CVWorkplaceProject.objects.create(workplace=workplace, project=project)

        # Start tests

        # `project` fail tests (project bigger)
        def _check_cases(inst, cases):
            for cname, attrs in cases.items():
                inst.refresh_from_db()
                for attr, val in attrs.items():
                    setattr(inst, attr, val)

                with self.subTest(f'bad values - {cname}'):
                    with self.assertRaises(IntegrityError) as exc:
                        with atomic():
                            inst.save()
                    self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        # CHECK constraint failed: cv_cvproject_begin_end_range_lte_workplace
        proj_test_cases = {
            '1. project is bigger than workplace (`end` is fixed)': {'end': wpe + datetime.timedelta(1)},
            '2. project is bigger than workplace (`end` is null)': {'end': None},
            '3. project is bigger than workplace (`begin` is less)': {'begin': wpb - datetime.timedelta(1)}
        }

        # The `project` date range is larger than the `workplace`
        _check_cases(project, proj_test_cases)

        # CHECK constraint failed: cv_cvworkplace_begin_end_range_gte_project
        project.refresh_from_db()
        wp_test_cases = {
            '1. workplace less than project (`end` is less)': {'end': project.end - datetime.timedelta(1)},
            '2. workplace less than project (`begin` is greater)': {'begin': project.begin + datetime.timedelta(1)}
        }

        # The `workplace` date range is smaller than the `project`
        _check_cases(workplace, wp_test_cases)

        # test success values
        project.refresh_from_db()
        workplace.refresh_from_db()
        with self.subTest('success values - project less then workplace (end is fixed)'):
            project.end = workplace.end - datetime.timedelta(5)
            project.save()

        with self.subTest('success values - workplace greater project (end is null)'):
            workplace.end = None
            workplace.save()

        with self.subTest('success values - project end is null and workplace end is null also'):
            project.end = None
            project.save()

    def test_13_crossing_for_different_users(self):
        """
            Tests CVEducation, CVProject, CVWorkplace begin..end ranges that crosses for different Users (profiles).
            Crosses for different users are allowed.
        """

        def _check_models(model: Type[Model], kw_init: dict, other_profile):
            obj = model.objects.create(**kw_init)
            self.assertIsNotNone(obj.pk)

            with self.subTest(f'`{model.__name__}` right - range crossing for different users is allowed'):
                obj1 = model.objects.create(** kw_init | {'profile': other_profile, 'end': None})
                self.assertIsNotNone(obj1.pk)

            # Change itself (allowed)
            with self.subTest(f'`{model.__name__}` right - modify itself is allowed'):
                obj.end = None
                obj.save()

            with self.subTest(f'`{model.__name__}` bad - range is crossing'):
                with self.assertRaises(IntegrityError) as exc:
                    with atomic():
                        model.objects.create(** kw_init | {'end': kw_init['end']+datetime.timedelta(1)})
                # CHECK constraint failed: cv_cveducation_begin_end_dates_intersect (`cv_cveducation` is varying)
                self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        cv_profile1 = cv_models.CVUserProfile.objects.create(user=self.user)
        user_1 = get_user_model().objects.create_user('test_1', email='test1@email.lan', password='12345678')
        cv_profile2 = cv_models.CVUserProfile.objects.create(user=user_1)

        today = datetime.date.today()
        begin = today - datetime.timedelta(7)
        end = today + datetime.timedelta(3)

        # test - CVEducation
        kw_edu = {
            'profile': cv_profile1, 'begin': begin, 'end': end,
            'institution': '...INSTITUTION...', 'speciality': '...SPECIALITY...', 'degree': '..DEGREE..',
            'complete': True,
        }
        _check_models(cv_models.CVEducation, kw_edu, cv_profile2)

        # test - CVProject
        kw_proj = {
            'profile': cv_profile1, 'begin': begin, 'end': end,
            'title': '...TITLE...', 'description': '...DESCRIPTION...',
            'prerequisite': '...PREREQUISITE...', 'result': '...RESULT...',
        }
        _check_models(cv_models.CVProject, kw_proj, cv_profile2)

        # test - CVWorkplace
        kw_wp = {
            'profile': cv_profile1, 'begin': begin, 'end': end, 'workplace': '...WORKPLACE...',
        }
        _check_models(cv_models.CVWorkplace, kw_wp, cv_profile2)

    def test_14_project_workplace_greater_children(self):
        """
            Tests CVProject.[begin..end] greater than CVProjectTechnology.duration,
            CVWorkplace.[begin..end] greater than CVWorkplaceResponsibility.[begin..end]
            when changing `begin` or `end` values in CVProject or CVWorkplace correspondingly
        """

        def _check_models(pobj: Model, cobj: Model, prepare_cback: callable):
            pname, cname = type(pobj).__name__, type(cobj).__name__

            with self.subTest(f'`{pname}` bad - `begin` is greater'):
                with self.assertRaises(IntegrityError) as exc:
                    with atomic():
                        pobj.begin = pobj.begin + datetime.timedelta(1)
                        pobj.save()
                # CHECK constraint failed: cv_project_begin_end_range_gte_projtech
                # CHECK constraint failed: cv_cvworkplace_begin_end_range_gte_wpresp
                self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

            pobj.refresh_from_db()
            with self.subTest(f'`{pname}` bad - `end` is smaller'):
                with self.assertRaises(IntegrityError) as exc:
                    with atomic():
                        pobj.end = pobj.end - datetime.timedelta(1)
                        pobj.save()
                # CHECK constraint failed: cv_project_begin_end_range_gte_projtech
                # CHECK constraint failed: cv_cvworkplace_begin_end_range_gte_wpresp
                self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

            with self.subTest(f'`{pname}` right - `end` is Null ({cname}.[end|duration] is fixed)'):
                    pobj.end = None
                    pobj.save()

            prepare_cback(pobj, cobj)

            with self.subTest(f'`{pname}` right - `end` is Null ({cname}.[end|duration] is Null)'):
                pobj.end = None
                pobj.save()

            with self.subTest(f'`{pname}` bad - `end` is smaller ({cname}.[end|duration] is Null)'):
                with self.assertRaises(IntegrityError) as exc:
                    with atomic():
                        pobj.end = end
                        pobj.save()
                # CHECK constraint failed: cv_project_begin_end_range_gte_projtech
                # CHECK constraint failed: cv_cvworkplace_begin_end_range_gte_wpresp
                self.assertTrue(str(exc.exception).startswith('CHECK constraint failed:'))

        cv_profile = cv_models.CVUserProfile.objects.create(user=self.user)

        today = datetime.date.today()
        begin = today - datetime.timedelta(7)
        end = today + datetime.timedelta(3)

        # test - CVProject
        proj = cv_models.CVProject.objects.create(
            profile=cv_profile, begin=begin, end=end,
            title='...TITLE...', description='...DESCRIPTION...',
            prerequisite='...PREREQUISITE...', result='...RESULT...',
        )
        self.assertIsNotNone(proj.pk)

        projtech = cv_models.CVProjectTechnology.objects.create(
            project=proj, technology=CVTechnologies.objects.create(technology='...TECHNOLOGY...'),
            duration=end - begin, notes='...NOTES...'
        )
        self.assertIsNotNone(projtech.pk)

        def _proj_prepare_cback(proj: Model, projtech: Model):
            # preparation for proj.end is Null and projtech.duration is Null also
            proj.end = None
            proj.save()

            projtech.duration = None
            projtech.save()

        _check_models(proj, projtech, _proj_prepare_cback)

        # test - CVWorkplace
        wp = cv_models.CVWorkplace.objects.create(profile=cv_profile, begin=begin, end=end, workplace='...WORKPLACE...')
        self.assertIsNotNone(proj.pk)

        wpresp = cv_models.CVWorkplaceResponsibility.objects.create(
            workplace=wp, begin=begin, end=end, responsibility='...RESPONSIBILITY...', role='...ROLE...',
        )
        self.assertIsNotNone(projtech.pk)

        def _wp_prepare_cback(wp: Model, wpresp: Model):
            # preparation for wp.end is Null and wpresp.end is Null also
            wp.end = None
            wp.save()

            wpresp.end = None
            wpresp.save()

        _check_models(wp, wpresp, _wp_prepare_cback)
