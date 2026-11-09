from django.contrib import admin
from django.db import models
from unfold.admin import ModelAdmin

from .models import Society


@admin.register(Society)
class SocietyAdmin(ModelAdmin):
    list_display = ["name", "slug", "phone", "founded_year", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
