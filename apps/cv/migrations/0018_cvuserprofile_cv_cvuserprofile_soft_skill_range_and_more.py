# Generated by Django 4.2.5 on 2023-10-17 13:43

from django.db import migrations, models
import django.db.models.functions.text
import django.db.models.lookups


class Migration(migrations.Migration):

    dependencies = [
        ('cv', '0017_cvuserprofile_cover_letter_cvuserprofile_position_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='cvuserprofile',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('soft_skill'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('soft_skill'))), (models.Value(0), models.Value(1024)))), name='cv_cvuserprofile_soft_skill_range'),
        ),
        migrations.AddConstraint(
            model_name='cvuserprofile',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('summary_qualification'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('summary_qualification'))), (models.Value(0), models.Value(2048)))), name='cv_cvuserprofile_summary_qualification_range'),
        ),
        migrations.AddConstraint(
            model_name='cvuserprofile',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('position'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('position'))), (models.Value(0), models.Value(248)))), name='cv_cvuserprofile_position_range'),
        ),
        migrations.AddConstraint(
            model_name='cvuserprofile',
            constraint=models.CheckConstraint(check=models.Q(django.db.models.lookups.IsNull(models.F('cover_letter'), False), django.db.models.lookups.Range(django.db.models.functions.text.Length(django.db.models.functions.text.Trim(models.F('cover_letter'))), (models.Value(0), models.Value(8192)))), name='cv_cvuserprofile_cover_letter_range'),
        ),
    ]
