from django.urls import path

from .views import articles, summary

urlpatterns = [
    path("summary/", summary, name="dataset-summary"),
    path("articles/", articles, name="dataset-articles"),
]
