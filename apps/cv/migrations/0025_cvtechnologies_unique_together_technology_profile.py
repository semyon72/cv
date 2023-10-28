# Generated by Django 4.2.5 on 2023-10-26 07:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cv', '0024_cvtechnologies_cv_cvtechnologies_technology_range_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='cvtechnologies',
            constraint=models.UniqueConstraint(fields=('technology', 'profile'), name='unique_together_technology_profile'),
        ),
    ]