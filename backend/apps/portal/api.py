"""
Beneficiary endpoints (/api/v1/me/...): a family sees only its own data.

The household is found through the logged-in account (Household.users), so
there is no id in the URL that someone could change to see another family.
"""

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import SocietyScopedMixin
from apps.registry.qr import household_qr_token

from . import selectors
from . import serializers as s


class MyFamilyView(SocietyScopedMixin, APIView):
    def household(self):
        household = selectors.household_of(self.request.user)
        if household is None:
            raise Http404("Your account is not linked to a household.")
        return household


class MyHouseholdView(MyFamilyView):
    @extend_schema(responses=s.MyHouseholdSerializer)
    def get(self, request):
        household = self.household()
        return Response(s.MyHouseholdSerializer(household).data)


class MySummaryView(MyFamilyView):
    @extend_schema(parameters=[OpenApiParameter("year", int)], responses=s.SummarySerializer)
    def get(self, request):
        try:
            year = int(request.query_params["year"]) if "year" in request.query_params else None
        except ValueError:
            year = None
        return Response(s.SummarySerializer(selectors.household_summary(self.household(), year)).data)


class MyQRView(MyFamilyView):
    @extend_schema(responses=s.QRSerializer)
    def get(self, request):
        household = self.household()
        return Response({"household_code": household.code, "qr_token": household_qr_token(household)})
