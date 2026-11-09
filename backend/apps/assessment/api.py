"""
Assessment API (/api/v1/assessments/...).

Volunteers submit surveys from the field; the President approves them.
Business rules live in services.py; who sees what in selectors.py.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.roles import has_any_role
from apps.core.api import SocietyScopedMixin
from apps.core.serializers import ReasonSerializer

from . import selectors, services
from . import serializers as s
from .models import Assessment
from .survey import QUESTIONS


class CanUseAssessments(BasePermission):
    message = "Only the President, the Program Coordinator and volunteers can use surveys."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.society_id and has_any_role(user, *services.SUBMIT_ROLES)
        )


class AssessmentViewSet(
    SocietyScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [CanUseAssessments]
    queryset = Assessment.objects.none()  # tells the API docs the model; get_queryset() is used for real
    filterset_fields = ["household", "status"]

    def get_queryset(self):
        qs = Assessment.objects.select_related("household", "submitted_by", "approved_by")
        return selectors.assessments_for(self.request.user, qs)

    def get_serializer_class(self):
        if selectors.can_see_scores(self.request.user):
            return s.AssessmentWithScoreSerializer
        return s.AssessmentSerializer

    def _out(self, assessment, code=status.HTTP_200_OK):
        return Response(self.get_serializer_class()(assessment).data, status=code)

    @extend_schema(responses=s.QuestionSerializer(many=True))
    @action(detail=False, methods=["get"], pagination_class=None)
    def survey(self, request):
        """The survey questions (English and Urdu), so the app can draw the form."""
        return Response(s.QuestionSerializer(QUESTIONS, many=True).data)

    @extend_schema(request=s.AssessmentCreateSerializer, responses={201: s.AssessmentSerializer})
    def create(self, request):
        data = s.AssessmentCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        assessment = services.submit_assessment(
            society=request.user.society, user=request.user, **data.validated_data
        )
        return self._out(assessment, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=s.AssessmentWithScoreSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._out(services.approve_assessment(self.get_object(), request.user))

    @extend_schema(request=ReasonSerializer, responses=s.AssessmentWithScoreSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        reason = ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        return self._out(
            services.reject_assessment(self.get_object(), request.user, reason.validated_data["reason"])
        )
