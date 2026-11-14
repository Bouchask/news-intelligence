import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from bigdata.classification.train import train_experiment
from bigdata.spark.classification import train_spark_naive_bayes
from bigdata.spark.data import read_articles
from bigdata.spark.session import create_spark_session
from bigdata.spark.topics import fit_lda_topics

from .models import Experiment, TopicRun

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="experiments.train")
def train_experiment_task(self, experiment_id: str) -> dict[str, object]:
    experiment = Experiment.objects.get(pk=experiment_id)
    experiment.status = Experiment.Status.RUNNING
    experiment.started_at = timezone.now()
    experiment.save(update_fields=("status", "started_at"))
    try:
        config = experiment.configuration
        if experiment.algorithm == "spark_naive_bayes":
            spark = create_spark_session("news-intelligence-spark-nb")
            try:
                result = train_spark_naive_bayes(
                    spark=spark,
                    dataset_path=experiment.dataset_path,
                    artifact_root=settings.MODEL_ARTIFACT_DIR,
                    experiment_id=str(experiment.pk),
                    selector=config.get("selector", "none"),
                    random_state=int(config.get("random_state", 42)),
                    test_size=float(config.get("test_size", 0.2)),
                    folds=int(config.get("folds", 5)),
                    max_features=int(config.get("max_features", 5000)),
                    k_features=int(config.get("k_features", 500)),
                )
            finally:
                spark.stop()
        else:
            result = train_experiment(
                dataset_path=experiment.dataset_path,
                artifact_root=settings.MODEL_ARTIFACT_DIR,
                experiment_id=str(experiment.pk),
                algorithm=experiment.algorithm,
                selector=config.get("selector", "none"),
                random_state=int(config.get("random_state", 42)),
                test_size=float(config.get("test_size", 0.2)),
                folds=int(config.get("folds", 5)),
                max_features=int(config.get("max_features", 5000)),
                k_features=int(config.get("k_features", 500)),
            )
        experiment.metrics = result["metrics"]
        experiment.confusion_matrix = result["confusion_matrix"]
        experiment.artifact_path = result["artifact_path"]
        experiment.status = Experiment.Status.SUCCEEDED
        experiment.finished_at = timezone.now()
        experiment.save(update_fields=("metrics", "confusion_matrix", "artifact_path", "status", "finished_at"))
        return {"experiment_id": str(experiment.pk), "status": experiment.status}
    except Exception as exc:
        logger.exception("Training failed for experiment %s", experiment.pk)
        experiment.status = Experiment.Status.FAILED
        experiment.error_message = str(exc)[:4000]
        experiment.finished_at = timezone.now()
        experiment.save(update_fields=("status", "error_message", "finished_at"))
        raise


@shared_task(bind=True, name="experiments.train_topics")
def train_topics_task(self, topic_run_id: str) -> dict[str, object]:
    run = TopicRun.objects.get(pk=topic_run_id)
    run.status = TopicRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=("status", "started_at"))
    spark = None
    try:
        spark = create_spark_session("news-intelligence-lda")
        articles = read_articles(spark, run.dataset_path)
        artifact_path = settings.MODEL_ARTIFACT_DIR / "topics" / str(run.pk)
        result = fit_lda_topics(spark, articles, artifact_path, num_topics=run.num_topics, max_iter=run.max_iter)
        run.results = {key: value for key, value in result.items() if key not in {"distribution_path", "artifact_path"}}
        run.artifact_path = result["artifact_path"]
        run.distribution_path = result["distribution_path"]
        run.status = TopicRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save(update_fields=("results", "artifact_path", "distribution_path", "status", "finished_at"))
        return {"topic_run_id": str(run.pk), "status": run.status}
    except Exception as exc:
        logger.exception("Spark LDA failed for topic run %s", run.pk)
        run.status = TopicRun.Status.FAILED
        run.error_message = str(exc)[:4000]
        run.finished_at = timezone.now()
        run.save(update_fields=("status", "error_message", "finished_at"))
        raise
    finally:
        if spark is not None:
            spark.stop()
