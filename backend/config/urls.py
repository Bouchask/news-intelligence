from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/datasets/", include("apps.datasets.urls")),
    path("api/v1/news/", include("apps.newsfeed.urls")),
    path("api/v1/", include("apps.experiments.urls")),
    path("api/v1/system/", include("apps.system_monitoring.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
