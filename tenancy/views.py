from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from defects.authz import actor_from_user

from .models import Tenant
from .serializers import TenantRegisterSerializer
from .services import add_tenant_domain, register_tenant
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


def _require_platform_admin(request) -> None:
    if not is_public_schema_context(request):
        raise PermissionDenied("Tenant management is only available from the public schema.")
    if not actor_from_user(request.user).is_platform_admin:
        raise PermissionDenied("Only platform admins can manage tenants.")


def platform_home(request):
    return redirect("platform-tenant-list")


def platform_login(request):
    next_url = request.GET.get("next") or reverse("platform-tenant-list")
    if request.user.is_authenticated and actor_from_user(request.user).is_platform_admin:
        return redirect(next_url)

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Invalid username or password.")
        elif not actor_from_user(user).is_platform_admin:
            messages.error(request, "Only platform admins can access the tenant console.")
        else:
            login(request, user)
            return redirect(request.POST.get("next") or reverse("platform-tenant-list"))

    return render(request, "tenancy/platform_login.html", {"next": next_url})


def platform_logout(request):
    logout(request)
    messages.success(request, "Signed out.")
    return redirect("platform-login")


def platform_tenant_list(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('platform-login')}?next={request.get_full_path()}")
    _require_platform_admin(request)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "create_tenant":
            _handle_create_tenant(request)
        elif action == "add_domain":
            _handle_add_domain(request)
        else:
            messages.error(request, "Unknown platform action.")
        return redirect("platform-tenant-list")

    tenants = Tenant.objects.prefetch_related("domains").order_by("schema_name")
    return render(
        request,
        "tenancy/tenant_console.html",
        {
            "tenants": tenants,
            "public_domains": settings.PUBLIC_SCHEMA_DOMAINS,
        },
    )


def _handle_create_tenant(request) -> None:
    try:
        tenant = register_tenant(
            schema_name=request.POST.get("schema_name", ""),
            domain=request.POST.get("domain", ""),
            name=request.POST.get("name", ""),
        )
    except ValidationError as exc:
        detail = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        messages.error(request, detail)
        return

    messages.success(request, f"Tenant {tenant.schema_name} created.")


def _handle_add_domain(request) -> None:
    tenant = Tenant.objects.filter(pk=request.POST.get("tenant_id")).first()
    if tenant is None:
        messages.error(request, "Tenant not found.")
        return

    try:
        domain = add_tenant_domain(
            tenant=tenant,
            domain=request.POST.get("domain", ""),
            is_primary=(request.POST.get("is_primary") == "on"),
        )
    except ValidationError as exc:
        detail = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        messages.error(request, detail)
        return

    messages.success(request, f"Domain {domain.domain} added to {tenant.schema_name}.")
