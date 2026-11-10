from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter()
router.register("", api.ApplicationViewSet, basename="application")

applications_urls = router.urls
