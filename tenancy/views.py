from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from defects.authz import actor_from_user

from .serializers import TenantRegisterSerializer
from .services import register_tenant
from .utils import is_public_schema_context

try:
    from drf_spectacular.utils import OpenApiExample, extend_schema
except Exception:  # pragma: no cover - optional dependency fallback

    class OpenApiExample:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    def extend_schema(*args, **kwargs):  # type: ignore[override]
        def _decorator(obj):
            return obj

        return _decorator


class TenantRegisterApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register tenant",
        description="Only platform admins can register tenants from the public schema.",
        request=TenantRegisterSerializer,
        responses={
            201: {"type": "object"},
            400: {"type": "object"},
            403: {"type": "object"},
            404: {"type": "object"},
        },
        examples=[
            OpenApiExample(
                "Register tenant example",
                value={"schema_name": "team_a", "domain": "team-a.betatrax.local", "name": "Team A"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        if not is_public_schema_context(request):
            return Response(
                {"error": "Tenant registration is only available from the public schema."},
                status=status.HTTP_404_NOT_FOUND,
            )

        actor = actor_from_user(request.user)
        if not actor.is_platform_admin:
            return Response({"error": "Only platform admins can register tenants."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TenantRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data
        try:
            tenant = register_tenant(
                schema_name=payload.get("schema_name", ""),
                domain=payload.get("domain", ""),
                name=payload.get("name", ""),
            )
        except ValidationError as exc:
            detail = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"error": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "Tenant registered successfully.",
                "tenant": {
                    "schema_name": tenant.schema_name,
                    "domain": tenant.domain,
                    "name": tenant.name,
                    "is_active": tenant.is_active,
                },
            },
            status=status.HTTP_201_CREATED,
        )
