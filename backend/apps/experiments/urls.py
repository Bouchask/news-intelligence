from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/overview/", views.dashboard_overview, name="dashboard-overview"),
    path("experiments/", views.experiment_list, name="experiment-list"),
    path("experiments/train/", views.train, name="experiment-train"),
    path("experiments/compare/", views.experiment_compare, name="experiment-compare"),
    path("analytics/topics/", views.topic_list, name="topic-list"),
    path("analytics/topics/run/", views.topic_train, name="topic-train"),
    path("analytics/topics/<uuid:topic_run_id>/", views.topic_detail, name="topic-detail"),
    path("pipelines/preprocess/", views.preprocess_article, name="text-preprocess"),
    path("experiments/<uuid:experiment_id>/", views.experiment_detail, name="experiment-detail"),
    path("experiments/<uuid:experiment_id>/register/", views.experiment_register, name="experiment-register"),
    path("models/", views.model_list, name="model-list"),
    path("models/active/", views.active_model, name="active-model"),
    path("models/<uuid:model_id>/activate/", views.model_activate, name="model-activate"),
    path("predictions/classify/", views.classify, name="prediction-classify"),
    path("predictions/", views.prediction_history, name="prediction-history"),
]
