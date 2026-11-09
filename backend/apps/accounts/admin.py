from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm

from .models import User
from .phone import normalize_phone


class PhoneCleanMixin:
    def clean_phone(self):
        try:
            return normalize_phone(self.cleaned_data["phone"])
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc


class UserCreateForm(PhoneCleanMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["phone", "name", "society"]


class UserEditForm(PhoneCleanMixin, UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserEditForm
    add_form = UserCreateForm
    change_password_form = AdminPasswordChangeForm

    list_display = ["name", "phone", "society", "is_staff", "is_active", "last_login"]
    list_filter = ["society", "is_staff", "is_active", "groups"]
    search_fields = ["name", "phone"]
    ordering = ["name"]
    filter_horizontal = ["groups", "user_permissions"]

    fieldsets = [
        (None, {"fields": ["phone", "password"]}),
        ("Profile", {"fields": ["name", "society", "language"]}),
        ("Roles & access", {"fields": ["is_active", "is_staff", "is_superuser", "groups"]}),
        ("Extra permissions", {"classes": ["collapse"], "fields": ["user_permissions"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["phone", "name", "society", "password1", "password2"]}),
    ]
    readonly_fields = ["last_login", "date_joined"]


# Show Django's Group (our "roles") with the Unfold look.
admin.site.unregister(Group)


@admin.register(Group)
class RoleAdmin(ModelAdmin):
    search_fields = ["name"]
    filter_horizontal = ["permissions"]
