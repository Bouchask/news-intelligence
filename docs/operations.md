# Operations guide

## Startup checklist

1. Activate `.venv`, install `requirements.txt`, and install frontend packages.
2. Set `.env` values and provide a valid labeled corpus.
3. `docker compose up -d redis kafka kafka-ui` and wait for healthy status.
4. In `backend/`, run `python manage.py migrate` and `python manage.py runserver`.
5. In another backend terminal, run `celery -A config worker --loglevel=INFO --pool=solo`.
6. Run the frontend with `npm run dev` from `frontend/`.
7. Import live BBC headline metadata, train/register/activate a model, create Kafka topics, start the three Kafka consumers, then replay saved items from the dashboard.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django signing key; set a private random local value | development-only key in settings |
| `DJANGO_DEBUG` | Local debug mode | `true` |
| `DATABASE_URL` | Optional database override | SQLite file in backend |
| `REDIS_URL` | Celery broker | `redis://localhost:6379/0` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka address for host processes | `localhost:9092` |
| `BBC_DATASET_PATH` | Labeled corpus path | `datasets/raw` |
| `BBC_NEWS_API_URL` | Unofficial metadata API root | `https://bbc-news-api.vercel.app` |
| `MODEL_ARTIFACT_DIR` | Trained model storage | `ml_artifacts` |
| `SPARK_MASTER` | Spark execution target | `local[*]` |

For processes running inside Compose, use `kafka:19092` as the Kafka bootstrap address. Never commit `.env`, databases, downloaded articles, or generated model artifacts.

## Operational endpoints

- `/api/v1/system/health/`: Django plus database check.
- `/api/v1/system/services/`: DB, Redis, Spark installation and Kafka socket reachability.
- `/api/v1/system/jobs/`: queued/running training and topic jobs.
- `/api/v1/system/streaming/`: broker/topic check and database-backed handled-event, prediction and DLQ counts.
- `/api/docs/`: interactive schema.

## Common recovery

- **No dataset:** check `BBC_DATASET_PATH`, then run `python -m bigdata.cli PATH` from repository root. A real labeled CSV or category folders are required.
- **No Celery queue:** `docker compose up -d redis`; check `REDIS_URL`; launch the worker. Foreground training: `python manage.py train_model --algorithm naive_bayes`.
- **BBC upstream outage:** retry later or use an API response snapshot for local debugging. The third-party service is outside this project's control.
- **Kafka topics missing:** run `python manage.py create_kafka_topics` after the broker reports healthy.
- **No active model:** train successfully, register the experiment, and activate its model version before running classifier consumer.
- **Messages in DLQ:** read `news.raw.dlq` or `news.classification.dlq` using Kafka tools, correct the source/configuration issue, and republish a corrected event. The app does not automatically replay DLQ data.
- **Spark driver startup:** confirm Java/PySpark compatibility and local socket binding. PySpark being installed is not proof that a Spark job has completed successfully.

## Local data and privacy

Current BBC summaries and links are persisted locally and sent through the configured local Kafka broker when replay is requested. No full BBC page scraping is performed. Keep downloaded datasets and generated database/artifact files on ignored local paths and follow the dataset/source terms applicable to your use.
