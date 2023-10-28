import datetime
import pathlib
from copy import copy
from os.path import splitext

from django.contrib.auth import get_user_model
from django.core.files.storage import Storage
from django.db import models

from .model_constraint import (
    add_constraints, length_range_constraint, date_end_gte_begin_or_null_constraint,
    education_dates_crossing_constraint, project_dates_crossing_constraint,
    project_technology_duration_in_project_constraint, workplace_dates_crossing_constraint,
    workplace_responsibility_dates_in_workplace_constraint, workplace_project_same_user_constraint,
    workplace_project_project_dates_in_workplace_constraint,
    workplace_dates_gte_project_constraint, project_dates_lte_workplace_constraint,
    workplace_dates_gte_workplace_responsibility, project_dates_gte_project_technology,
    workplace_responsibility_dates_crossing_constraint, technology_unique_together_with_profile,
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


def profile_photo_upload_to(profile: "CVUserProfile", filename):

    # get old file [*type(profile).objects.filter(pk=profile.pk)][0].photo.file
    # it will generate {FileNotFoundError}[Errno 2] ->
    #   No such file or directory: '/home/.../media/hedgehog-1215140_960_720.jpg_wrong.jpg'
    # if database contains file name that is not related to the real file.
    #
    # Disadvantage - one extra SQL request.
    #
    # `profile.photo._committed` ->
    # indicates that whether the file (filename) has already been committed to the database or not.
    #
    # For now, the best algorithm is to drop the old file if it exists and
    # hope that saving to the database will be successful.

    dst_filename = '{}_{}{}'.format(profile.user.username, profile.user.pk, pathlib.Path(filename).suffix)
    storage: Storage = profile.photo.storage
    to_clear = [profile.photo]
    if profile.pk:
        try:
            to_clear.append(type(profile).objects.get(pk=profile.pk).photo)
        except Exception as exc:
            if isinstance(exc, type(profile).DoesNotExist):
                pass
            else:
                raise exc

    # cleanup both for the normal case and for the case that someone inserted the file manually
    for p in to_clear:
        if p.name:
            storage.delete(p.name)

    return dst_filename


@add_constraints(
    soft_skill=length_range_constraint,
    summary_qualification=length_range_constraint,
    position=length_range_constraint,
    cover_letter=length_range_constraint,
)
class CVUserProfile(CVAbstractBaseModel):
    """
        We add additional fields to the registered user.
        Make sure that the standard user has first_name, last_name and email.
    """
    # Probably: need set primary_key = True to have same pk as related User and reduce number of queries
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    birthday = models.DateField(null=True, blank=True, default=None)
    photo = models.ImageField(null=True, blank=True, default=None, upload_to=profile_photo_upload_to)
    soft_skill = models.TextField(max_length=1024, null=True, blank=True, default=None)
    summary_qualification = models.TextField(max_length=2*1024, null=True, blank=True, default=None)
    position = models.CharField(max_length=248, null=True, blank=True, default=None)
    cover_letter = models.TextField(max_length=8*1024, null=True, blank=True, default=None)


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
    title=length_range_constraint,
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
    title = models.CharField(max_length=248)
    prerequisite = models.CharField(max_length=248, blank=True)
    description = models.TextField(max_length=8*1024)
    result = models.CharField(max_length=248, blank=True)
    # TODO: probably, can add default= func_to_get_begin from CVWorkplace through CVWorkplaceProject
    begin = models.DateField(default=datetime.date.today)
    end = models.DateField(null=True, default=None, blank=True)


@add_constraints(
    technology=[length_range_constraint, technology_unique_together_with_profile],
    technology_type=length_range_constraint
)
class CVTechnologies(CVAbstractBaseModel):
    """
        Dictionary like (for all users):
        'Python', 'SQL', 'Oracle' etc
    """
    class TechnologyTypes(models.TextChoices):
        PROGRAMMING_LANGUAGE = ('PROG_LANG', 'Programming language')
        FRAMEWORK_LIBRARY = ('FWRK_LIB', 'Framework/Library')
        FORMAT = ('FORMAT', 'Format')
        DATABASE = ('DB', 'Database')
        OPERATING_SYSTEM = ('OS', 'Operating System')
        DEVELOPMENT_TOOL = ('DEV_TOOL', 'Development tool')
        PROTOCOL = ('PROTOCOL', 'Protocol')
        OTHER = ('OTHER', 'Other')

    TECHNOLOGY_TYPES_DEFAULT_CHOICE = TechnologyTypes.OTHER

    technology = models.CharField(max_length=48)
    technology_type = models.CharField(
        max_length=10, choices=TechnologyTypes.choices, default=TECHNOLOGY_TYPES_DEFAULT_CHOICE
    )
    profile = models.ForeignKey(CVUserProfile, on_delete=models.CASCADE, null=True, default=None, blank=True)

    class Meta(CVAbstractBaseModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=['technology', 'profile'], name='unique_together_technology_profile')
        ]
        unique_together = ['technology', 'profile']


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
    notes = models.CharField(max_length=248, null=True, blank=True, default=None)

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
    responsibility=length_range_constraint,
    begin__end=[date_end_gte_begin_or_null_constraint, workplace_responsibility_dates_crossing_constraint],
    workplace__begin__end=workplace_responsibility_dates_in_workplace_constraint,
)
class CVWorkplaceResponsibility(CVAbstractBaseModel):
    """
        Duties (responsibilities) of the user in the place where he worked.
        And role type, for example: Python Engineer, DBA and so on.
    """
    workplace = models.ForeignKey(CVWorkplace, on_delete=models.CASCADE)
    # TODO: Probably (discussable), should be changed to `models.CharField(max_length=248)`
    #  because a lot of information can be described in `Project.description`
    #  but in a complex case it matters (much projects in one workplace with career growth or change of responsibility)
    #  For now, We currently limit it to 1024 characters using `constraint`
    responsibility = models.TextField(max_length=1024)
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
