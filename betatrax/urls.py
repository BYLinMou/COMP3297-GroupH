"""
URL configuration for betatrax project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path
from defects.views import DeveloperEffectivenessApi, ProductRegisterApi, TenantRegisterApi

try:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
except Exception:  # pragma: no cover - optional dependency fallback
    SpectacularAPIView = None
    SpectacularSwaggerView = None

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/defects/', include('defects.urls')),
    path('api/products/register/', ProductRegisterApi.as_view(), name='api-product-register-root'),
    path('api/tenants/register/', TenantRegisterApi.as_view(), name='api-tenant-register-root'),
    path(
        'api/developers/<str:developer_id>/effectiveness/',
        DeveloperEffectivenessApi.as_view(),
        name='api-developer-effectiveness',
    ),
    path('', include('frontend.urls')),
]

if SpectacularAPIView is not None and SpectacularSwaggerView is not None:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    ]

if not settings.DEBUG:
    urlpatterns += [
        path(
            "static/<path:path>",
            staticfiles_serve,
            {"insecure": True},
        )
    ]
