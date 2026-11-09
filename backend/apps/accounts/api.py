from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import MeSerializer, PhoneTokenObtainSerializer


class LoginView(TokenObtainPairView):
    """POST phone + password → access and refresh tokens."""

    serializer_class = PhoneTokenObtainSerializer
    throttle_scope = "login"


class MeView(RetrieveUpdateAPIView):
    """The logged-in user's profile and roles. The mobile app uses `roles` to pick a dashboard."""

    serializer_class = MeSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user
