"""
Admin helpers shared by every module.

The admin panel never bypasses business rules: forms run the service's
check_can_* function in clean(), and admin actions call service functions.
"""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from unfold.admin import ModelAdmin

from .exceptions import BusinessRuleError


def error_text(exc) -> str:
    return getattr(exc, "message", None) or str(exc)


def user_society(request):
    return getattr(request.user, "society", None)


def run_service(modeladmin, request, queryset, fn, done: str):
    """Call a service for each selected row and report successes and errors."""
    ok = 0
    for obj in queryset:
        try:
            fn(obj)
            ok += 1
        except (BusinessRuleError, PermissionDenied) as exc:
            modeladmin.message_user(request, f"{obj}: {error_text(exc)}", messages.ERROR)
    if ok:
        modeladmin.message_user(request, f"{ok} {done}.", messages.SUCCESS)


def ask_reason(modeladmin, request, queryset, action: str, title: str, fn, done: str, label: str = "Reason"):
    """Show a page asking for a reason (or other short text) first; run the service when it's submitted."""
    if request.POST.get("apply"):
        reason = request.POST.get("reason", "")
        run_service(modeladmin, request, queryset, lambda obj: fn(obj, request.user, reason), done)
        return None
    return TemplateResponse(
        request,
        "admin/reason_form.html",
        {
            **modeladmin.admin_site.each_context(request),
            "title": title,
            "queryset": queryset,
            "action": action,
            "label": label,
        },
    )


class ServiceCheckedForm(forms.ModelForm):
    """Runs the service's check_can_* function in clean(), so rule errors show on the form."""

    request = None  # set by ServiceAdmin.get_form()
    check_on_change = False  # by default only new records are checked

    def check(self, cleaned_data):  # override
        pass

    def clean(self):
        cleaned = super().clean()
        if (self.instance._state.adding or self.check_on_change) and not self.errors:
            try:
                self.check(cleaned)
            except (BusinessRuleError, PermissionDenied) as exc:
                raise forms.ValidationError(error_text(exc)) from exc
        return cleaned


def with_request(form_class, request):
    """A copy of the form class that knows the current request (forms don't get it by default)."""
    if isinstance(form_class, type) and hasattr(form_class, "request"):
        return type(form_class.__name__, (form_class,), {"request": request})
    return form_class


class ServiceAdmin(ModelAdmin):
    """Base admin: nothing is deleted; new rows get the user's society and created_by."""

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        return with_request(super().get_form(request, obj, **kwargs), request)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.society = user_society(request)
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
