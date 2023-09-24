from django.contrib import admin

# Register your models here.
from apps.cv.models import CVUserProfile


class CVUserAdmin(admin.ModelAdmin):
    pass

admin.site.register(CVUserProfile, CVUserAdmin)
