from django.urls import path

from . import views

app_name = "frontend"

urlpatterns = [
    path("", views.home, name="home"),
    path("auth/", views.external_auth, name="external-auth"),
    path("auth/logout/", views.sign_out, name="sign-out"),
    path("products/register/", views.register_product, name="register-product"),
    path("defects/new/", views.create_defect, name="create-defect"),
    path("<str:defect_id>/", views.defect_detail, name="defect-detail"),
]
