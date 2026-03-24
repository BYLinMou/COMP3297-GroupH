from django.urls import path

from . import views

app_name = "frontend"

urlpatterns = [
    path("", views.home, name="home"),
    path("auth/", views.external_auth, name="external-auth"),
    path("defects/new/", views.create_defect, name="create-defect"),
    path("<str:defect_id>/", views.defect_detail, name="defect-detail"),
]
