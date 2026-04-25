from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import register_product
from .authz import actor_from_user
from .models import DefectReport, Product
from django.core.exceptions import ValidationError
from .serializers import DefectActionSerializer, DefectCreateSerializer, TenantRegisterSerializer
from .services import (
    STATUS_BY_SLUG,
    apply_action,
    create_defect,
    register_tenant,
    serialize_defect_detail_for_api,
    serialize_defect_for_api,
    summarize_developer_effectiveness,
)

try:
    from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
except Exception:  # pragma: no cover - optional dependency fallback
    class OpenApiExample:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    class OpenApiParameter:  # type: ignore[override]
        QUERY = "query"

        def __init__(self, *args, **kwargs):
            pass

    def extend_schema(*args, **kwargs):  # type: ignore[override]
        def _decorator(obj):
            return obj

        return _decorator

class ProductRegisterApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register product",
        description="Only Product Owners can register a product and bind developer accounts in one request.",
        request={
            "application/json": {
                "type": "object",
                "required": ["product_id", "name"],
                "properties": {
                    "product_id": {"type": "string"},
                    "name": {"type": "string"},
                    "developers": {"type": "array", "items": {"type": "string"}},
                },
            }
        },
        responses={201: {"type": "object"}, 400: {"type": "object"}, 403: {"type": "object"}},
        examples=[
            OpenApiExample(
                "Register product example",
                value={"product_id": "Prod_2", "name": "BetaTrax Mobile", "developers": ["dev-004"]},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        actor = actor_from_user(request.user)
        if not actor.is_owner:
            return Response({"error": "Only Product Owner can register products"}, status=403)

        try:
            product = register_product(
                owner_user=request.user,
                product_id=request.data.get('product_id'),
                product_name=request.data.get('name'),
                developer_ids=request.data.get('developers', [])
            )
            return Response({"message": "Product registered successfully", "product_id": product.product_id}, status=201)
        except ValidationError as e:
            detail = e.messages[0] if getattr(e, "messages", None) else str(e)
            return Response({"error": detail}, status=400)
        
class DefectCreateApi(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    @extend_schema(
        summary="Submit defect",
        description="Create a new defect report from an external testing system.",
        request=DefectCreateSerializer,
        responses={201: {"type": "object"}, 400: {"type": "object"}, 404: {"type": "object"}},
    )
    def post(self, request):


        serializer = DefectCreateSerializer(data=request.data)
        if not serializer.is_valid():
            details = serializer.errors
            if "missing_fields" in details:
                return Response(
                    {"error": "Missing required fields.", "missing_fields": details["missing_fields"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"error": details}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data
        product = Product.objects.filter(product_id=payload["product_id"]).first()
        if product is None:
            return Response({"error": "Unknown Product ID."}, status=status.HTTP_404_NOT_FOUND)

        defect = create_defect(
            {
                "product": product,
                "version": payload["version"],
                "title": payload["title"],
                "description": payload["description"],
                "steps": payload["steps"],
                "tester_id": payload["tester_id"],
                "email": payload.get("email", ""),
            }
        )

        return Response(
            {
                "report_id": defect.report_id,
                "status": defect.status,
                "required_fields": ["product_id", "version", "title", "description", "steps", "tester_id"],
            },
            status=status.HTTP_201_CREATED,
        )


class DefectListApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List defects",
        description="List defects by filters. Product Owners and Developers have different visibility scopes.",
        parameters=[
            OpenApiParameter(name="status", location=OpenApiParameter.QUERY, required=False, type=str),
            OpenApiParameter(name="product_id", location=OpenApiParameter.QUERY, required=False, type=str),
            OpenApiParameter(name="owner_id", location=OpenApiParameter.QUERY, required=False, type=str),
            OpenApiParameter(name="developer_id", location=OpenApiParameter.QUERY, required=False, type=str),
        ],
        responses={200: {"type": "object"}, 403: {"type": "object"}},
    )
    def get(self, request):
        actor = actor_from_user(request.user)
        if not actor.is_owner and not actor.is_developer:
            return Response({"error": "Only Product Owner or Developer can view defects."}, status=status.HTTP_403_FORBIDDEN)

        queryset = DefectReport.objects.select_related("product").order_by("-received_at")

        status_value = str(request.query_params.get("status", "")).strip()
        if status_value:
            desired = STATUS_BY_SLUG.get(status_value.lower().replace(" ", "-"), status_value)
            if actor.is_developer and desired == "New":
                return Response({"error": "Developer cannot access New defects."}, status=status.HTTP_403_FORBIDDEN)
            queryset = queryset.filter(status=desired)

        product_id = str(request.query_params.get("product_id", "")).strip()
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        owner_id = str(request.query_params.get("owner_id", "")).strip()
        if owner_id:
            if not actor.is_owner or owner_id != actor.actor_id:
                return Response({"error": "owner_id must match authenticated Product Owner."}, status=status.HTTP_403_FORBIDDEN)

        developer_id = str(request.query_params.get("developer_id", "")).strip()
        if developer_id:
            if not actor.is_developer or developer_id != actor.actor_id:
                return Response({"error": "developer_id must match authenticated Developer."}, status=status.HTTP_403_FORBIDDEN)

        if actor.is_owner:
            queryset = queryset.filter(product__owner_id=actor.actor_id)
        else:
            queryset = queryset.filter(product__developers__developer_id=actor.actor_id).distinct()

        return Response({"items": [serialize_defect_for_api(defect) for defect in queryset]})


class DefectDetailApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get defect detail",
        description="Retrieve detailed defect information by report_id.",
        responses={200: {"type": "object"}, 403: {"type": "object"}, 404: {"type": "object"}},
    )
    def get(self, request, defect_id):
        defect = DefectReport.objects.select_related("product").filter(report_id=defect_id).first()
        if defect is None:
            return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)

        actor = actor_from_user(request.user)
        if not actor.is_owner and not actor.is_developer:
            return Response({"error": "Only Product Owner or Developer can view defect details."}, status=status.HTTP_403_FORBIDDEN)

        if actor.is_owner:
            if defect.product.owner_id != actor.actor_id:
                return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            if defect.status == "New":
                return Response({"error": "Developer cannot access New defects."}, status=status.HTTP_403_FORBIDDEN)
            if not defect.product.developers.filter(developer_id=actor.actor_id).exists():
                return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(serialize_defect_detail_for_api(defect))


class DefectActionApi(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    @extend_schema(
        summary="Apply defect action",
        description=(
            "Supported actions: accept_open, reject, duplicate, take_ownership, set_fixed, "
            "cannot_reproduce, set_resolved, reopen, add_comment."
        ),
        request=DefectActionSerializer,
        responses={200: {"type": "object"}, 400: {"type": "object"}, 403: {"type": "object"}, 404: {"type": "object"}},
    )
    def post(self, request, defect_id):
        defect = DefectReport.objects.select_related("product").filter(report_id=defect_id).first()
        if defect is None:
            return Response({"error": "Defect not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DefectActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data
        actor = actor_from_user(request.user)
        if not actor.actor_id:
            return Response({"error": "Authentication required."}, status=status.HTTP_403_FORBIDDEN)
        action = str(payload.get("action", "")).strip()
        try:
            message = apply_action(defect, action, payload, actor)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": message,
                "report_id": defect.report_id,
                "status": defect.status,
            }
        )


class TenantRegisterApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register tenant",
        description="Only platform admins can register tenants with schema_name and domain.",
        request=TenantRegisterSerializer,
        responses={201: {"type": "object"}, 400: {"type": "object"}, 403: {"type": "object"}},
        examples=[
            OpenApiExample(
                "Register tenant example",
                value={"schema_name": "team_a", "domain": "team-a.betatrax.local", "name": "Team A"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
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


class DeveloperEffectivenessApi(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Developer effectiveness",
        description="Only Product Owners can query effectiveness classification for developers in their teams.",
        responses={200: {"type": "object"}, 400: {"type": "object"}, 403: {"type": "object"}},
    )
    def get(self, request, developer_id):
        actor = actor_from_user(request.user)
        if not actor.is_owner:
            return Response({"error": "Only product owners can view developer effectiveness."}, status=status.HTTP_403_FORBIDDEN)

        try:
            result = summarize_developer_effectiveness(actor.actor_id, developer_id)
        except ValidationError as exc:
            detail = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"error": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)
