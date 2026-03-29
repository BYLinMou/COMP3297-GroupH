from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authz import actor_from_user
from .models import DefectReport, Product
from .serializers import DefectActionSerializer, DefectCreateSerializer
from .services import STATUS_BY_SLUG, apply_action, create_defect, ensure_demo_seed, serialize_defect_for_api


class DefectCreateApi(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        ensure_demo_seed()

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

    def get(self, request):
        ensure_demo_seed()
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
        elif actor.is_developer:
            queryset = queryset.filter(product__developers__developer_id=actor.actor_id).distinct()

        return Response({"items": [serialize_defect_for_api(defect) for defect in queryset]})


class DefectActionApi(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, defect_id):
        ensure_demo_seed()
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
