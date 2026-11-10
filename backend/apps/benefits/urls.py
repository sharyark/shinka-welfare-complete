from rest_framework.routers import SimpleRouter

from apps.programs.api import ProgramViewSet

from . import api

router = SimpleRouter()
router.register("programs", ProgramViewSet, basename="program")
router.register("cycles", api.CycleViewSet, basename="cycle")
router.register("enrollments", api.EnrollmentViewSet, basename="enrollment")
router.register("entitlements", api.EntitlementViewSet, basename="entitlement")

benefits_urls = router.urls
