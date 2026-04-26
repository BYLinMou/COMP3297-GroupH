from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import path
from tenancy.views import TenantRegisterApi, platform_home, platform_login, platform_logout, platform_tenant_list

try:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
except Exception:  # pragma: no cover - optional dependency fallback
    SpectacularAPIView = None
    SpectacularSwaggerView = None


urlpatterns = [
    path("", platform_home, name="platform-home"),
    path("platform/login/", platform_login, name="platform-login"),
    path("platform/logout/", platform_logout, name="platform-logout"),
    path("admin/", admin.site.urls),
    path("platform/tenants/", platform_tenant_list, name="platform-tenant-list"),
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
