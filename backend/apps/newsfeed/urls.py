from django.urls import path

from .views import import_live, live_items

urlpatterns = [
    path("live/", live_items, name="live-news-list"),
    path("live/import/", import_live, name="live-news-import"),
]
