"""
Admin panel for households.

Like finance, the admin never skips the rules: forms run the service checks,
saving calls the services, and Verify / Reject / Reopen / Archive are actions
that call service functions. Households are never deleted (archive instead).
CNIC numbers are typed in once and only ever shown masked.
"""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils.html import format_html_join
from unfold.admin import StackedInline
from unfold.decorators import display

from apps.accounts.models import User
from apps.core.admin_tools import (
    ServiceAdmin,
    ServiceCheckedForm,
    ask_reason,
    error_text,
    run_service,
    user_society,
    with_request,
)
from apps.core.exceptions import BusinessRuleError

from . import selectors, services
from .cnic import normalize_cnic
from .models import Household, Member, Mohalla
from .serializers import MEMBER_FIELDS

STATUS_COLORS = {"pending": "warning", "verified": "success", "rejected": "danger", "archived": "info"}


@admin.register(Mohalla)
class MohallaAdmin(ServiceAdmin):
    list_display = ["name", "name_ur", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "name_ur"]
    fields = ["name", "name_ur", "is_active"]


# --- Members (edited inside the household page) ------------------------------------


class MemberForm(forms.ModelForm):
    cnic = forms.CharField(
        label="CNIC / B-form number",
        required=False,
        help_text="Type it to add or replace (e.g. 37101-1234567-3). It is stored encrypted.",
    )
    request = None  # set by MemberInline.get_formset()

    class Meta:
        model = Member
        fields = MEMBER_FIELDS

    def clean_cnic(self):
        raw = self.cleaned_data.get("cnic", "")
        return normalize_cnic(raw) if raw.strip() else ""

    def _post_clean(self):
        super()._post_clean()  # fills self.instance from the form
        if self.errors or not self.has_changed() or self.cleaned_data.get("DELETE"):
            return
        try:
            # One-head is checked by the formset, which sees all members together.
            services.check_member(
                self.instance,
                user=self.request.user,
                cnic=self.cleaned_data.get("cnic") or None,
                check_head=False,
            )
        except (BusinessRuleError, PermissionDenied) as exc:
            self.add_error(None, error_text(exc))


class MemberFormSet(forms.BaseInlineFormSet):
    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.instance.household = self.instance
        if form.instance._state.adding:
            form.instance.society_id = self.instance.society_id or getattr(
                user_society(form.request), "pk", None
            )
        return form

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        kept = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        heads = [f for f in kept if f.cleaned_data.get("relation") == Member.Relation.HEAD]
        if kept and len(heads) != 1:
            raise ValidationError("A household needs exactly one head of household.")


class MemberInline(StackedInline):
    model = Member
    form = MemberForm
    formset = MemberFormSet
    fields = [
        ("full_name", "father_or_husband_name"),
        ("relation", "gender", "date_of_birth"),
        ("cnic", "cnic_masked"),
        ("is_earning", "occupation"),
        ("is_disabled", "is_orphan", "is_widow"),
        ("education_level", "school"),
    ]
    readonly_fields = ["cnic_masked"]

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if obj is None else 0

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form = with_request(formset.form, request)
        return formset

    def has_delete_permission(self, request, obj=None):
        # Only fix mistakes while the household is still awaiting verification.
        return obj is None or obj.status == Household.Status.PENDING


# --- Households ----------------------------------------------------------------------


class HouseholdForm(ServiceCheckedForm):
    check_on_change = True
    consent = forms.BooleanField(
        required=False,
        label="Consent given",
        help_text="The family agreed to their information (and photos) being recorded.",
    )

    class Meta:
        model = Household
        fields = ["mohalla", "address", "phone", "latitude", "longitude", "notes", "users"]

    def check(self, cleaned):
        if self.instance._state.adding:
            services.check_can_register(
                society=user_society(self.request),
                user=self.request.user,
                mohalla=cleaned["mohalla"],
                consent=cleaned.get("consent", False),
            )
        else:
            services.check_can_edit(self.instance, self.request.user)


@admin.register(Household)
class HouseholdAdmin(ServiceAdmin):
    form = HouseholdForm
    inlines = [MemberInline]
    list_display = ["code", "head_name", "mohalla", "phone", "member_count", "status_badge"]
    list_filter = ["status", "mohalla"]
    search_fields = ["code"]  # the real search is selectors.search_households (name, phone, CNIC)
    search_help_text = "Search by code, phone, member name or full CNIC."
    actions = ["verify", "reject", "reopen", "archive"]
    decision_fields = [
        "code",
        "status",
        "possible_duplicates",
        "registered_by",
        "consent_given_at",
        "verified_by",
        "verified_at",
        "decision_note",
    ]

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["consent", *HouseholdForm.Meta.fields]
        return [*self.decision_fields, *HouseholdForm.Meta.fields]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        if obj.status == Household.Status.ARCHIVED:
            return [*self.decision_fields, *HouseholdForm.Meta.fields]
        return self.decision_fields

    def get_queryset(self, request):
        qs = selectors.households_for(request.user, super().get_queryset(request))
        return selectors.with_summary(qs)

    def get_search_results(self, request, queryset, search_term):
        return selectors.search_households(queryset, search_term), False

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "users":  # only this society's app accounts
            kwargs["queryset"] = User.objects.filter(society=user_society(request))
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if change:
            obj.save()
        else:
            services.create_household(
                obj, society=user_society(request), user=request.user, consent=form.cleaned_data["consent"]
            )

    def save_formset(self, request, form, formset, change):
        formset.save(commit=False)  # builds the objects; the services save them
        for member in formset.deleted_objects:
            services.remove_member(member, user=request.user)
        changed = [
            f
            for f in formset.forms
            if f.has_changed() and f.cleaned_data and not f.cleaned_data.get("DELETE")
        ]
        # Save non-heads first, so swapping the head never has two heads at once.
        changed.sort(key=lambda f: f.instance.relation == Member.Relation.HEAD)
        for f in changed:
            services.save_member(f.instance, user=request.user, cnic=f.cleaned_data.get("cnic") or None)

    @display(description="Head of household")
    def head_name(self, obj):
        return obj.head_name or "—"

    @display(description="Members", ordering="member_count")
    def member_count(self, obj):
        return obj.member_count

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Possible duplicates")
    def possible_duplicates(self, obj):
        others = selectors.possible_duplicates(obj)
        if not others:
            return "None found (same phone, or same name and father/husband name)."
        return format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            ((reverse("admin:registry_household_change", args=[h.pk]), h.code) for h in others),
        )

    @admin.action(description="Verify selected households", permissions=["change"])
    def verify(self, request, queryset):
        run_service(self, request, queryset, lambda h: services.verify_household(h, request.user), "verified")

    @admin.action(description="Reject selected households", permissions=["change"])
    def reject(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reject", "Reject households", services.reject_household, "rejected"
        )

    @admin.action(description="Reopen selected rejected households", permissions=["change"])
    def reopen(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reopen", "Reopen households", services.reopen_household, "reopened"
        )

    @admin.action(description="Archive selected households (no longer helped)", permissions=["change"])
    def archive(self, request, queryset):
        return ask_reason(
            self, request, queryset, "archive", "Archive households", services.archive_household, "archived"
        )
