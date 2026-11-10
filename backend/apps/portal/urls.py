from django.urls import path

from . import api

portal_urls = [
    path("household/", api.MyHouseholdView.as_view(), name="me-household"),
    path("summary/", api.MySummaryView.as_view(), name="me-summary"),
    path("qr/", api.MyQRView.as_view(), name="me-qr"),
]
