from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter()
router.register("mohallas", api.MohallaViewSet, basename="mohalla")
router.register("households", api.HouseholdViewSet, basename="household")
router.register("members", api.MemberViewSet, basename="member")

registry_urls = router.urls
