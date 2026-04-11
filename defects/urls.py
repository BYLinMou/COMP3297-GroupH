from django.urls import path

from .views import DefectActionApi, DefectCreateApi, DefectDetailApi, DefectListApi, ProductRegisterApi

app_name = "defects"

urlpatterns = [
    path("", DefectListApi.as_view(), name="api-list-defects"),
    path("new/", DefectCreateApi.as_view(), name="api-create-defect"),
    path("<str:defect_id>/", DefectDetailApi.as_view(), name="api-defect-detail"),
    path("<str:defect_id>/actions/", DefectActionApi.as_view(), name="api-defect-action"),
    path("products/register/", ProductRegisterApi.as_view(), name="api-product-register"),
]
