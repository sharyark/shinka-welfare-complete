"""
Admin panel for programs.

The Cycle screen is registered in apps/benefits/admin.py, because its actions
(generate benefits, close) belong to the benefits app, and programs must not
import benefits. It still appears under "Programs" in the menu.
"""

from django.contrib import admin

from apps.core.admin_tools import ServiceAdmin

from .models import Program


@admin.register(Program)
class ProgramAdmin(ServiceAdmin):
    list_display = [
        "name",
        "name_ur",
        "kind",
        "target",
        "unit",
        "default_amount",
        "min_need_score",
        "fund",
        "is_active",
    ]
    list_filter = ["kind", "target", "is_active"]
    search_fields = ["name", "name_ur", "code"]
    prepopulated_fields = {"code": ["name"]}
    fieldsets = [
        (None, {"fields": ["name", "name_ur", "code", "description", "is_active"]}),
        (
            "What is given",
            {"fields": ["kind", "target", "unit", "default_quantity", "default_amount", "fund"]},
        ),
        (
            "Who is eligible",
            {
                "fields": [
                    "requires_application",
                    "min_need_score",
                    "member_min_age",
                    "member_max_age",
                    "member_gender",
                ]
            },
        ),
    ]

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)
        if not change:  # model.clean() needs the society to check the fund
            obj.society = request.user.society
        return obj
