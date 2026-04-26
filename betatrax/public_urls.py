from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import path
from tenancy.views import TenantRegisterApi

try:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
except Exception:  # pragma: no cover - optional dependency fallback
    SpectacularAPIView = None
    SpectacularSwaggerView = None


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/tenants/register/", TenantRegisterApi.as_view(), name="api-tenant-register-root"),
]

if SpectacularAPIView is not None and SpectacularSwaggerView is not None:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    ]

if not settings.DEBUG:
    urlpatterns += [
        path(
            "static/<path:path>",
            staticfiles_serve,
            {"insecure": True},
        )
    ]
