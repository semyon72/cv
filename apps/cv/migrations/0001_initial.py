# Generated by Django 4.2.5 on 2023-09-24 01:55

import apps.cv.db_functions
import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.text
import django.db.models.lookups


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CVEducation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('begin', models.DateField(default=datetime.date.today)),
                ('end', models.DateField(blank=True, default=None, null=True)),
                ('institution', models.CharField(max_length=248)),
                ('speciality', models.CharField(max_length=248)),
                ('degree', models.CharField(max_length=24)),
                ('complete', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVHobby',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVLanguage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lang', models.CharField(max_length=24)),
                ('level', models.CharField(max_length=24)),
                ('notes', models.CharField(max_length=248)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=248)),
                ('prerequisite', models.CharField(max_length=248)),
                ('result', models.CharField(max_length=48)),
                ('begin', models.DateField(default=datetime.date.today)),
                ('end', models.DateField(blank=True, default=None, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVProjectTechnology',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('duration', models.DurationField(blank=True, null=True)),
                ('notes', models.CharField(max_length=248)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVResources',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resource', models.CharField(max_length=24, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVTechnologies',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('technology', models.CharField(max_length=24, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVUserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('birthday', models.DateField(blank=True, default=None, null=True)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVWorkplace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workplace', models.CharField(max_length=248)),
                ('begin', models.DateField(default=datetime.date.today)),
                ('end', models.DateField(blank=True, default=None, null=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvuserprofile')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVWorkplaceResponsibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('responsibility', models.TextField()),
                ('role', models.CharField(max_length=48)),
                ('begin', models.DateField(default=datetime.date.today)),
                ('end', models.DateField(blank=True, default=None, null=True)),
                ('workplace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvworkplace')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVWorkplaceProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='cv.cvproject')),
                ('workplace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvworkplace')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CVUserResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('link', models.CharField(max_length=248)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvuserprofile')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvresources')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='cvtechnologies',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('technology'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('technology'))), (models.Value(1), models.Value(24)))), name='cv_cvtechnologies_technology_range'),
        ),
        migrations.AddConstraint(
            model_name='cvresources',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('resource'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('resource'))), (models.Value(1), models.Value(24)))), name='cv_cvresources_resource_range'),
        ),
        migrations.AddField(
            model_name='cvprojecttechnology',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvproject'),
        ),
        migrations.AddField(
            model_name='cvprojecttechnology',
            name='technology',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvtechnologies'),
        ),
        migrations.AddField(
            model_name='cvproject',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvuserprofile'),
        ),
        migrations.AddField(
            model_name='cvlanguage',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvuserprofile'),
        ),
        migrations.AddField(
            model_name='cvhobby',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvuserprofile'),
        ),
        migrations.AddField(
            model_name='cveducation',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cv.cvuserprofile'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplaceresponsibility',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('role'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('role'))), (models.Value(1), models.Value(48)))), name='cv_cvworkplaceresponsibility_role_range'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplaceresponsibility',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('begin'), False), models.Q(django.db.models.lookups.IsNull(models.F('end'), True), django.db.models.lookups.GreaterThanOrEqual(models.F('end'), models.F('begin')), _connector='OR')), name='cv_cvworkplaceresponsibility_begin_end_gte_begin_or_null'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplaceresponsibility',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.WorkplaceRespDatesCrossing(models.F('id'), models.F('workplace_id'), models.F('begin'), models.F('end'), output_field=models.BooleanField()), models.Value(False)), name='cv_cvworkplaceresponsibility_begin_end_date_range_intersection'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplaceresponsibility',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.WorkplaceRespDatesInWorkplace(models.F('workplace_id'), models.F('begin'), models.F('end'), output_field=models.IntegerField()), models.Value(1)), name='cv_cvworkplaceresponsibility_workplace_id_range_in_workplace'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplaceproject',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.WorkplaceProjectSameUser(models.F('workplace_id'), models.F('project_id'), output_field=models.IntegerField()), models.Value(1)), name='cv_cvworkplaceproject_workplace_id_project_same_user'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplaceproject',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.WorkplaceProjectProjectDatesInWorkplace(models.F('workplace_id'), models.F('project_id'), output_field=models.IntegerField()), models.Value(1)), name='cv_cvworkplaceproject_workplace_id_project_duration'),
        ),
        migrations.AlterUniqueTogether(
            name='cvworkplaceproject',
            unique_together={('workplace', 'project')},
        ),
        migrations.AddConstraint(
            model_name='cvworkplace',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('workplace'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('workplace'))), (models.Value(1), models.Value(248)))), name='cv_cvworkplace_workplace_range'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplace',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('begin'), False), models.Q(django.db.models.lookups.IsNull(models.F('end'), True), django.db.models.lookups.GreaterThanOrEqual(models.F('end'), models.F('begin')), _connector='OR')), name='cv_cvworkplace_begin_end_gte_begin_or_null'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplace',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.WorkplaceDatesCrossing(models.F('id'), models.F('profile_id'), models.F('begin'), models.F('end'), output_field=models.IntegerField()), models.Value(0)), name='cv_cvworkplace_begin_end_dates_intersect'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplace',
            constraint=models.CheckConstraint(check=apps.cv.db_functions.WorkplaceDatesGTEProject(models.F('id'), models.F('begin'), models.F('end'), output_field=models.BooleanField()), name='cv_cvworkplace_begin_end_range_gte_project'),
        ),
        migrations.AddConstraint(
            model_name='cvworkplace',
            constraint=models.CheckConstraint(check=apps.cv.db_functions.WorkplaceDatesGTEWorkplaceResp(models.F('id'), models.F('begin'), models.F('end'), output_field=models.BooleanField()), name='cv_cvworkplace_begin_end_range_gte_wpresp'),
        ),
        migrations.AlterUniqueTogether(
            name='cvuserresource',
            unique_together={('profile', 'resource')},
        ),
        migrations.AddConstraint(
            model_name='cvprojecttechnology',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('notes'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('notes'))), (models.Value(1), models.Value(248)))), name='cv_cvprojecttechnology_notes_range'),
        ),
        migrations.AddConstraint(
            model_name='cvprojecttechnology',
            constraint=models.CheckConstraint(check=apps.cv.db_functions.ProjectTechnologyDurationInProject(models.F('project_id'), models.F('duration'), output_field=models.BooleanField()), name='cv_cvprojecttechnology_duration_project_technology_check'),
        ),
        migrations.AlterUniqueTogether(
            name='cvprojecttechnology',
            unique_together={('project', 'technology')},
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('description'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('description'))), (models.Value(1), models.Value(248)))), name='cv_cvproject_description_range'),
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('prerequisite'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('prerequisite'))), (models.Value(1), models.Value(248)))), name='cv_cvproject_prerequisite_range'),
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('result'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('result'))), (models.Value(1), models.Value(48)))), name='cv_cvproject_result_range'),
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('begin'), False), models.Q(django.db.models.lookups.IsNull(models.F('end'), True), django.db.models.lookups.GreaterThanOrEqual(models.F('end'), models.F('begin')), _connector='OR')), name='cv_cvproject_begin_end_gte_begin_or_null'),
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.ProjectDatesCrossing(models.F('id'), models.F('profile_id'), models.F('begin'), models.F('end'), output_field=models.IntegerField()), models.Value(0)), name='cv_cvproject_begin_end_dates_intersect'),
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=apps.cv.db_functions.ProjectDatesLTEWorkplace(models.F('id'), models.F('begin'), models.F('end'), output_field=models.BooleanField()), name='cv_cvproject_begin_end_range_lte_workplace'),
        ),
        migrations.AddConstraint(
            model_name='cvproject',
            constraint=models.CheckConstraint(check=apps.cv.db_functions.ProjectDatesGTEProjectTechnology(models.F('id'), models.F('begin'), models.F('end'), output_field=models.BooleanField()), name='cv_cvproject_begin_end_range_gte_projtech'),
        ),
        migrations.AddConstraint(
            model_name='cvlanguage',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('lang'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('lang'))), (models.Value(1), models.Value(24)))), name='cv_cvlanguage_lang_range'),
        ),
        migrations.AddConstraint(
            model_name='cvlanguage',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('level'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('level'))), (models.Value(1), models.Value(24)))), name='cv_cvlanguage_level_range'),
        ),
        migrations.AddConstraint(
            model_name='cvlanguage',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('notes'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('notes'))), (models.Value(1), models.Value(248)))), name='cv_cvlanguage_notes_range'),
        ),
        migrations.AddConstraint(
            model_name='cveducation',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('institution'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('institution'))), (models.Value(1), models.Value(248)))), name='cv_cveducation_institution_range'),
        ),
        migrations.AddConstraint(
            model_name='cveducation',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('speciality'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('speciality'))), (models.Value(1), models.Value(248)))), name='cv_cveducation_speciality_range'),
        ),
        migrations.AddConstraint(
            model_name='cveducation',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('degree'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('degree'))), (models.Value(1), models.Value(24)))), name='cv_cveducation_degree_range'),
        ),
        migrations.AddConstraint(
            model_name='cveducation',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('begin'), False), models.Q(django.db.models.lookups.IsNull(models.F('end'), True), django.db.models.lookups.GreaterThanOrEqual(models.F('end'), models.F('begin')), _connector='OR')), name='cv_cveducation_begin_end_gte_begin_or_null'),
        ),
        migrations.AddConstraint(
            model_name='cveducation',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(apps.cv.db_functions.EducationDatesCrossing(models.F('id'), models.F('profile_id'), models.F('begin'), models.F('end'), output_field=models.IntegerField()), models.Value(0)), name='cv_cveducation_begin_end_dates_intersect'),
        ),
    ]
