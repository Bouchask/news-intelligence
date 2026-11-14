from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bigdata.classification.train import ALGORITHMS, SELECTORS, train_experiment

from apps.experiments.models import Experiment


class Command(BaseCommand):
    help = "Run one reproducible BBC classification experiment in the foreground (no Redis/Celery required)."

    def add_arguments(self, parser):
        parser.add_argument("--algorithm", choices=sorted(ALGORITHMS), default="naive_bayes")
        parser.add_argument("--selector", choices=sorted(SELECTORS), default="none")

    def handle(self, *args, **options):
        experiment = Experiment.objects.create(
            name=f"{options['algorithm'].replace('_', ' ').title()} · {options['selector']}",
            algorithm=options["algorithm"],
            dataset_path=str(settings.BBC_DATASET_PATH),
            configuration={"selector": options["selector"], "random_state": 42, "test_size": 0.2, "folds": 5},
            status=Experiment.Status.RUNNING,
            started_at=timezone.now(),
        )
        try:
            result = train_experiment(
                dataset_path=experiment.dataset_path,
                artifact_root=settings.MODEL_ARTIFACT_DIR,
                experiment_id=str(experiment.pk),
                algorithm=experiment.algorithm,
                selector=options["selector"],
            )
        except Exception as exc:
            experiment.status = Experiment.Status.FAILED
            experiment.error_message = str(exc)[:4000]
            experiment.finished_at = timezone.now()
            experiment.save(update_fields=("status", "error_message", "finished_at"))
            raise CommandError(f"Training failed: {exc}") from exc
        experiment.status = Experiment.Status.SUCCEEDED
        experiment.metrics = result["metrics"]
        experiment.confusion_matrix = result["confusion_matrix"]
        experiment.artifact_path = result["artifact_path"]
        experiment.finished_at = timezone.now()
        experiment.save(update_fields=("status", "metrics", "confusion_matrix", "artifact_path", "finished_at"))
        self.stdout.write(self.style.SUCCESS(f"Experiment {experiment.pk} complete: macro F1={result['metrics']['f1_macro']:.4f}"))
