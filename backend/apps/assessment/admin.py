"""
Admin panel for household surveys and need-score weights.

- Surveys are submitted through the service (score calculated there) and are
  read-only afterwards: to change answers, reject and submit a new survey.
- Weights ("Need factors") can be changed by the President; every change is kept
  (History button, django-simple-history).
- Volunteers never see scores, even in the admin.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from simple_history.admin import SimpleHistoryAdmin
from unfold.decorators import display

from apps.core.admin_tools import ServiceAdmin, ServiceCheckedForm, ask_reason, run_service, user_society

from . import selectors, services
from .models import Assessment, NeedFactor
from .survey import FACTORS_BY_CODE, QUESTIONS, QUESTIONS_BY_CODE

STATUS_COLORS = {"pending": "warning", "approved": "success", "rejected": "danger", "superseded": "info"}
YES_NO = [("yes", "Yes"), ("no", "No")]


@admin.register(NeedFactor)
class NeedFactorAdmin(SimpleHistoryAdmin, ServiceAdmin):
    list_display = ["factor", "points", "default_points"]
    fields = ["factor", "points"]
    readonly_fields = ["factor"]

    def has_add_permission(self, request):
        return False  # the list of factors is fixed in code (survey.FACTORS); only points change

    def changelist_view(self, request, extra_context=None):
        if society := user_society(request):
            services.ensure_factors(society)  # first visit creates the default weights
        return super().changelist_view(request, extra_context)

    @display(description="Factor")
    def factor(self, obj):
        return obj.get_code_display()

    @display(description="Default")
    def default_points(self, obj):
        return FACTORS_BY_CODE[obj.code].default_points


def _question_field(q):
    label = f"{q.label} · {q.label_ur}"
    if q.kind == "choice":
        return forms.ChoiceField(label=label, choices=[(c[0], f"{c[1]} · {c[2]}") for c in q.choices])
    if q.kind == "yes_no":
        return forms.ChoiceField(label=label, choices=YES_NO, widget=forms.RadioSelect)
    return forms.IntegerField(label=label, required=q.required, min_value=0)


class _AssessmentFormBase(ServiceCheckedForm):
    class Meta:
        model = Assessment
        fields = ["household", "notes"]

    def answers(self) -> dict:
        answers = {}
        for q in QUESTIONS:
            value = self.cleaned_data.get(q.code)
            answers[q.code] = (value == "yes") if q.kind == "yes_no" else value
        return answers

    def check(self, cleaned):
        services.check_can_submit(
            society=user_society(self.request), user=self.request.user, household=cleaned["household"]
        )


# One form field per survey question, declared on the class so the admin accepts them.
AssessmentForm = type(
    "AssessmentForm", (_AssessmentFormBase,), {q.code: _question_field(q) for q in QUESTIONS}
)


@admin.register(Assessment)
class AssessmentAdmin(ServiceAdmin):
    form = AssessmentForm
    autocomplete_fields = ["household"]
    list_filter = ["status"]
    search_fields = ["household__code"]
    actions = ["approve", "reject"]

    def get_list_display(self, request):
        columns = ["household", "status_badge", "submitted_by", "created_at", "valid_until"]
        return columns[:1] + ["score"] + columns[1:] if selectors.can_see_scores(request.user) else columns

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["household", *[q.code for q in QUESTIONS], "notes"]
        details = ["household", "status", "answers_table", "notes", "submitted_by", "created_at"]
        decision = ["approved_by", "approved_at", "valid_until", "decision_note"]
        if selectors.can_see_scores(request.user):
            details[2:2] = ["score", "breakdown_table"]
        return details + decision

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else self.get_fields(request, obj)  # frozen once submitted

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("household", "submitted_by")
        return selectors.assessments_for(request.user, qs)

    def save_model(self, request, obj, form, change):
        if not change:
            services.submit_assessment(
                society=user_society(request),
                user=request.user,
                household=form.cleaned_data["household"],
                answers=form.answers(),
                notes=form.cleaned_data.get("notes", ""),
                into=obj,
            )

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Answers")
    def answers_table(self, obj):
        rows = []
        for code, value in obj.answers.items():
            q = QUESTIONS_BY_CODE.get(code)
            if q is None:
                continue
            if q.kind == "yes_no":
                value = "Yes" if value else "No"
            elif q.kind == "choice":
                value = next((c[1] for c in q.choices if c[0] == value), value)
            rows.append((q.label, value))
        return format_html("<table>{}</table>", format_html_join("", "<tr><td>{}</td><td>{}</td></tr>", rows))

    @display(description="How the score was calculated")
    def breakdown_table(self, obj):
        if not obj.breakdown:
            return "No factor applied."
        return format_html(
            "<table>{}</table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>× {}</td><td>{:+d}</td></tr>",
                ((row["label"], row["count"], row["points"]) for row in obj.breakdown),
            ),
        )

    @admin.action(
        description="Approve selected surveys (need score counts from today)", permissions=["change"]
    )
    def approve(self, request, queryset):
        run_service(
            self, request, queryset, lambda a: services.approve_assessment(a, request.user), "approved"
        )

    @admin.action(description="Reject selected surveys", permissions=["change"])
    def reject(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reject", "Reject surveys", services.reject_assessment, "rejected"
        )
