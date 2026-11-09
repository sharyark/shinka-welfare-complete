from django.urls import path
from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter()
router.register("funds", api.FundViewSet, basename="fund")
router.register("donors", api.DonorViewSet, basename="donor")
router.register("donations", api.DonationViewSet, basename="donation")
router.register("expenses", api.ExpenseViewSet, basename="expense")

finance_urls = router.urls

public_urls = [
    path("<slug:slug>/transparency/", api.PublicTransparencyView.as_view(), name="public-transparency"),
    path("<slug:slug>/funds/", api.PublicFundsView.as_view(), name="public-funds"),
]
