from django.db import transaction

from .models import Experiment, RegisteredModel


@transaction.atomic
def register_experiment(experiment_id: str, name: str | None = None) -> RegisteredModel:
    experiment = Experiment.objects.select_for_update().get(pk=experiment_id)
    if experiment.status != Experiment.Status.SUCCEEDED or not experiment.artifact_path:
        raise ValueError("Only a successfully trained experiment with a saved artifact can be registered.")
    if existing := RegisteredModel.objects.filter(experiment=experiment).first():
        return existing
    model_name = (name or experiment.algorithm.replace("_", " ").title()).strip()[:180]
    latest = RegisteredModel.objects.filter(name=model_name).order_by("-version").first()
    next_version = latest.version + 1 if latest else 1
    return RegisteredModel.objects.create(
        name=model_name,
        version=next_version,
        algorithm=experiment.algorithm,
        experiment=experiment,
        artifact_path=experiment.artifact_path,
        metrics=experiment.metrics,
    )


@transaction.atomic
def activate_model(model_id: str) -> RegisteredModel:
    model = RegisteredModel.objects.select_for_update().get(pk=model_id)
    RegisteredModel.objects.exclude(pk=model.pk).update(is_active=False)
    if not model.is_active:
        model.is_active = True
        model.save(update_fields=("is_active",))
    return model
