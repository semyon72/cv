# IDE: PyCharm
# Project: cv
# Path: apps/cv
# File: views_extend_schema.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2024-01-05 (y-m-d) 3:54 PM

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiRequest

common_schema_description = 'The URI may contain an optional parameter {id} at the end. ' \
                            'Behaviour of the actions: POST has no {id} -> `create`; GET has no {id} -> `list`;' \
                            ' GET has {id} -> `retrieve`; DELETE, PUT, PATCH must have {id} paratemeter.'

education_schema = extend_schema(
    # parameters=[
    #     OpenApiParameter(
    #         name='id',
    #         description='unique identifier',
    #         required=False,
    #         type=OpenApiTypes.INT,
    #         location=OpenApiParameter.PATH,
    #     ),
    # ],
    description=common_schema_description
)

hobby_schema = education_schema
language_schema = education_schema
project_schema = education_schema
workplace_schema = education_schema
userresource_schema = education_schema
projecttechnology_schema = education_schema
workplaceresponsibility_schema = education_schema
workplaceproject_schema = education_schema
profile_schema = education_schema
