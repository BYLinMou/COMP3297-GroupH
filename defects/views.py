from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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
    permission_classes = [AllowAny]

    def get(self, request):
        ensure_demo_seed()
        queryset = DefectReport.objects.select_related("product").order_by("-received_at")

        status_value = str(request.query_params.get("status", "")).strip()
        if status_value:
            desired = STATUS_BY_SLUG.get(status_value.lower().replace(" ", "-"), status_value)
            queryset = queryset.filter(status=desired)

        product_id = str(request.query_params.get("product_id", "")).strip()
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        owner_id = str(request.query_params.get("owner_id", "")).strip()
        if owner_id:
            queryset = queryset.filter(product__owner_id=owner_id)

        developer_id = str(request.query_params.get("developer_id", "")).strip()
        if developer_id:
            queryset = queryset.filter(product__developers__developer_id=developer_id).distinct()

        return Response({"items": [serialize_defect_for_api(defect) for defect in queryset]})


class DefectActionApi(APIView):
    permission_classes = [AllowAny]

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
        action = str(payload.get("action", "")).strip()
        try:
            message = apply_action(defect, action, payload)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": message,
                "report_id": defect.report_id,
                "status": defect.status,
            }
        )
