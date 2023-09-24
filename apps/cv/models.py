import datetime

from django.contrib.auth import get_user_model
from django.db import models

from .model_constraint import (
    add_constraints, length_range_constraint, date_end_gte_begin_or_null_constraint,
    education_dates_crossing_constraint, project_dates_crossing_constraint,
    project_technology_duration_in_project_constraint, workplace_dates_crossing_constraint,
    workplace_responsibility_dates_in_workplace_constraint, workplace_project_same_user_constraint,
    workplace_project_project_dates_in_workplace_constraint,
    workplace_dates_gte_project_constraint, project_dates_lte_workplace_constraint,
    workplace_dates_gte_workplace_responsibility, project_dates_gte_project_technology,
    workplace_responsibility_dates_crossing_constraint,
)


class CVBaseModelMetaMixin:
    """
        For common purposes or like stub, for a stub example
        !!! Without constraints = [] doesn't work migrations along with @add_constraints
    """
    constraints = []


class CVAbstractBaseModel(models.Model):
    """
        For common purposes or like stub, for a stub example
        !!! Without constraints = [] doesn't work migrations along with @add_constraints
    """
    class Meta(CVBaseModelMetaMixin):
        abstract = True


class CVUserProfile(CVAbstractBaseModel):
    """
        We add additional fields to the registered user.
        Make sure that the standard user has first_name, last_name and email.
    """
    # Probably: need set primary_key = True to have same pk as related User and reduce number of queries
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    birthday = models.DateField(null=True, blank=True, default=None)
    photo = models.ImageField(null=True, blank=True)


@add_constraints(resource=length_range_constraint)
class CVResources(CVAbstractBaseModel):
    """
        Dictionary of available resources for all users, such as:
        'email' - contact, default login email
        'skype', 'site', 'linkedin', 'telegram',
        'telephone', 'upwork', 'facebook', 'tiktok',
        'instagram', 'tweeter', 'GitHub', 'GitLab' ....
    """
    resource = models.CharField(max_length=24, unique=True)


class CVUserResource(CVAbstractBaseModel):
    """
        Resources are associated with the user
        Each user can have 'GitHub', 'telephone' etc
    """
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
    resource = models.ForeignKey(CVResources, on_delete=models.CASCADE)
    link = models.CharField(max_length=248)

    class Meta(CVAbstractBaseModel.Meta):
        unique_together = ['profile', 'resource']


@add_constraints(
    institution=length_range_constraint,
    speciality=length_range_constraint,
    degree=length_range_constraint,
    begin__end=[date_end_gte_begin_or_null_constraint, education_dates_crossing_constraint],
)
class CVEducation(CVAbstractBaseModel):
    """
        Information on user education
    """
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
    begin = models.DateField(default=datetime.date.today)
    end = models.DateField(null=True, default=None, blank=True)
    institution = models.CharField(max_length=248)
    speciality = models.CharField(max_length=248)
    degree = models.CharField(max_length=24)
    complete = models.BooleanField(default=True)


@add_constraints(
    lang=length_range_constraint,
    level=length_range_constraint,
    notes=length_range_constraint,
)
class CVLanguage(CVAbstractBaseModel):
    """
        Information about languages and proficiency level
    """
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
    lang = models.CharField(max_length=24)
    level = models.CharField(max_length=24)
    notes = models.CharField(max_length=248)


class CVHobby(CVAbstractBaseModel):
    """
        Information about hobbies
    """
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True)


@add_constraints(
    description=length_range_constraint,
    prerequisite=length_range_constraint,
    result=length_range_constraint,
    begin__end=[
        date_end_gte_begin_or_null_constraint,
        project_dates_crossing_constraint,
        project_dates_lte_workplace_constraint,
        project_dates_gte_project_technology,
    ],
)
class CVProject(CVAbstractBaseModel):
    """
        Projects in which the user participated.
        `begin` - required.
        if `end` is null that means infinity (current time)
        `end` can be null only for most recent project.
        `begin` and `end` are not mandatory to calculate default CVProjectTechnology.duration but helpful
    """
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
    description = models.CharField(max_length=248)
    prerequisite = models.CharField(max_length=248)
    result = models.CharField(max_length=48)
    # TODO: probably, can add default= func_to_get_begin from CVWorkplace through CVWorkplaceProject
    begin = models.DateField(default=datetime.date.today)
    end = models.DateField(null=True, default=None, blank=True)


@add_constraints(technology=length_range_constraint)
class CVTechnologies(CVAbstractBaseModel):
    """
        Dictionary like (for all users):
        'Python', 'SQL', 'Oracle' etc
    """
    technology = models.CharField(max_length=24, unique=True)


@add_constraints(
    notes=length_range_constraint,
    project__duration=project_technology_duration_in_project_constraint
)
class CVProjectTechnology(CVAbstractBaseModel):
    """
        Technologies that were used (+duration and notes) in a certain project

        `duration` can be null just for parent who is null also. null - means infinity (current)
    """
    project = models.ForeignKey(CVProject, on_delete=models.CASCADE)
    technology = models.ForeignKey(CVTechnologies, on_delete=models.CASCADE)
    # TODO: probably, can add default= func_to_get_duration from parent (CVTechnologies)
    # `duration` can be null just for parent who is null also. null - means infinity (current)
    duration = models.DurationField(null=True, blank=True)
    notes = models.CharField(max_length=248)

    class Meta(CVAbstractBaseModel.Meta):
        unique_together = ['project', 'technology']


@add_constraints(
    workplace=length_range_constraint,
    begin__end=[
        date_end_gte_begin_or_null_constraint,
        workplace_dates_crossing_constraint,
        workplace_dates_gte_project_constraint,
        workplace_dates_gte_workplace_responsibility,
    ],
)
class CVWorkplace(CVAbstractBaseModel):
    """
        Place where user worked
    """
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE)
    workplace = models.CharField(max_length=248)
    begin = models.DateField(default=datetime.date.today)
    end = models.DateField(null=True, default=None, blank=True)


@add_constraints(
    role=length_range_constraint,
    begin__end=[date_end_gte_begin_or_null_constraint, workplace_responsibility_dates_crossing_constraint],
    workplace__begin__end=workplace_responsibility_dates_in_workplace_constraint,
)
class CVWorkplaceResponsibility(CVAbstractBaseModel):
    """
        Duties (responsibilities) of the user in the place where he worked.
        And role type, for example: Python Engineer, DBA and so on.
    """
    workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
    responsibility = models.TextField()
    role = models.CharField(max_length=48)
    begin = models.DateField(default=datetime.date.today)
    end = models.DateField(null=True, default=None, blank=True)


@add_constraints(
    workplace__project=[
        workplace_project_same_user_constraint,
        workplace_project_project_dates_in_workplace_constraint
    ],
)
class CVWorkplaceProject(CVAbstractBaseModel):
    """
        A table linking workplaces together with projects in which the user was involved at that time
    """
    workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
    project = models.OneToOneField(CVProject, on_delete=models.CASCADE)

    class Meta(CVAbstractBaseModel.Meta):
        unique_together = ['workplace', 'project']
