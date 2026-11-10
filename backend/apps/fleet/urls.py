from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter()
router.register("vehicles", api.VehicleViewSet, basename="vehicle")
router.register("trips", api.TripViewSet, basename="trip")

fleet_urls = router.urls
