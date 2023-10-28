# Generated by Django 4.2.5 on 2023-10-26 09:00

import apps.cv.db_functions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cv', '0025_cvtechnologies_unique_together_technology_profile'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='cvtechnologies',
            constraint=models.CheckConstraint(check=apps.cv.db_functions.TechnologyUniqueTogetherWithProfile(models.F('id'), models.F('technology'), models.F('profile_id'), output_field=models.BooleanField()), name='cv_cvtechnologies_technology_unique_together_with_profile'),
        ),
    ]