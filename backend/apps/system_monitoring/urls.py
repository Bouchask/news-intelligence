from django.urls import path

from .views import health, jobs, services, streaming_replay, streaming_status

urlpatterns = [
    path("health/", health, name="system-health"),
    path("services/", services, name="system-services"),
    path("jobs/", jobs, name="system-jobs"),
    path("streaming/", streaming_status, name="streaming-status"),
    path("streaming/replay/", streaming_replay, name="streaming-replay"),
]
