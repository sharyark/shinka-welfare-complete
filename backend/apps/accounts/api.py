from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import mobile_auth
from . import serializers as s
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


# --- Mobile login (architecture 13): SMS code once, then a PIN ------------------------


class PublicAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"


class RequestCodeView(PublicAuthView):
    """Sends an SMS code if the number has an account. The answer is the same either way."""

    @extend_schema(request=s.PhoneSerializer, responses={200: dict})
    def post(self, request):
        data = s.PhoneSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        mobile_auth.request_code(data.validated_data["phone"])
        return Response({"detail": "If this number is registered, a code has been sent by SMS."})


class VerifyCodeView(PublicAuthView):
    @extend_schema(request=s.VerifyCodeSerializer, responses=s.PinTokenSerializer)
    def post(self, request):
        data = s.VerifyCodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        token = mobile_auth.verify_code(data.validated_data["phone"], data.validated_data["code"])
        return Response({"pin_token": token})


class SetPinView(PublicAuthView):
    @extend_schema(request=s.SetPinSerializer, responses={200: dict})
    def post(self, request):
        data = s.SetPinSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        mobile_auth.set_pin(data.validated_data["pin_token"], data.validated_data["pin"])
        return Response({"detail": "PIN saved. You can now log in with it."})


class PinLoginView(PublicAuthView):
    @extend_schema(request=s.PinLoginSerializer, responses=s.TokenPairSerializer)
    def post(self, request):
        data = s.PinLoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        tokens = mobile_auth.pin_login(
            v["phone"],
            v["pin"],
            device_id=v["device_id"],
            name=v["device_name"],
            platform=v["platform"],
            push_token=v["push_token"],
        )
        return Response(tokens)
