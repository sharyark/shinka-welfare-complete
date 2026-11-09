"""
URL map.

/admin/          committee admin panel (Django Admin + Unfold)
/api/v1/...      REST API for the mobile app and public website
/api/schema/     OpenAPI file (mobile app generates its types from it)
/api/docs/       Swagger UI to try the API in a browser
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from apps.accounts.api import LoginView, MeView
from apps.core.api import HealthView
from apps.finance.urls import finance_urls, public_urls

api_v1 = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", TokenBlacklistView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("finance/", include(finance_urls)),
    path("public/", include(public_urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "api"), namespace="v1")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
