import uuid

from django.db import models


class Experiment(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    algorithm = models.CharField(max_length=40)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    dataset_path = models.CharField(max_length=1000)
    configuration = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict, blank=True)
    confusion_matrix = models.JSONField(default=dict, blank=True)
    artifact_path = models.CharField(max_length=1200, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"


class RegisteredModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    version = models.PositiveIntegerField()
    algorithm = models.CharField(max_length=40)
    experiment = models.ForeignKey(Experiment, on_delete=models.PROTECT, related_name="registered_models")
    artifact_path = models.CharField(max_length=1200)
    metrics = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("name", "-version")
        constraints = [models.UniqueConstraint(fields=("name", "version"), name="unique_registered_model_version")]

    def __str__(self) -> str:
        return f"{self.name}:v{self.version}"


class Prediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_version = models.ForeignKey(RegisteredModel, on_delete=models.PROTECT, related_name="predictions")
    content_sha256 = models.CharField(max_length=64, db_index=True)
    predicted_category = models.CharField(max_length=80, db_index=True)
    probabilities = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    latency_ms = models.FloatField()
    source_type = models.CharField(max_length=40, default="manual", db_index=True)
    event_id = models.CharField(max_length=128, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class KafkaEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"
        DEAD_LETTERED = "dead_lettered", "Dead lettered"

    event_id = models.CharField(max_length=128, primary_key=True)
    topic = models.CharField(max_length=180, db_index=True)
    event_type = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class TopicRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    num_topics = models.PositiveSmallIntegerField(default=8)
    max_iter = models.PositiveSmallIntegerField(default=30)
    dataset_path = models.CharField(max_length=1000)
    results = models.JSONField(default=dict, blank=True)
    artifact_path = models.CharField(max_length=1200, blank=True)
    distribution_path = models.CharField(max_length=1200, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
