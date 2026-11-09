from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter()
router.register("", api.AssessmentViewSet, basename="assessment")

assessment_urls = router.urls
