from django.urls import path
from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter()
router.register("", api.DistributionViewSet, basename="distribution")

distribution_urls = [
    path("lookup/", api.LookupView.as_view(), name="distribution-lookup"),
    path("deliver/", api.DeliverView.as_view(), name="distribution-deliver"),
    path("report/", api.ReportView.as_view(), name="distribution-report"),
    *router.urls,
]
