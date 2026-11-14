# Architecture and data flow

## Components

```mermaid
flowchart LR
  BBC[Unofficial BBC News API] -->|on-demand headlines and summaries| Django[Django API]
  Django --> DB[(SQLite by default / optional PostgreSQL)]
  React[React dashboard] --> Django
  Corpus[Licensed labeled corpus] --> Ingest[Python ingestion and EDA]
  Ingest --> Train[scikit-learn training]
  Train --> Artifacts[Versioned joblib artifacts]
  Artifacts --> Registry[Model registry in database]
  Django -->|saved headline replay| Raw[(Kafka news.raw)]
  Raw --> C1[Raw cleaner consumer]
  C1 --> Prep[(news.preprocessed)]
  C1 --> Requests[(classification requests)]
  Requests --> C2[Active model classifier]
  C2 --> Results[(classification results)]
  Results --> C3[Idempotent persistence consumer]
  C3 --> DB
  C1 -. invalid payload .-> DLQ[(Dead-letter topics)]
  C2 -. invalid/unprocessable .-> DLQ
  Django --> Redis[(Redis/Celery)]
  Redis --> Worker[Training and Spark LDA jobs]
  Worker --> DB
```

## Data boundaries

The live upstream provides current headline metadata and summaries, not guaranteed full article text. `LiveNewsItem` keeps its source URL, title, summary, image, sections, language and fetch snapshot time. It does not infer a publication time. Kafka messages use a stable BBC-link-derived document ID and snapshot-derived event ID. The event timestamp is when this application publishes the message.

Historical supervised labels come from the supplied labeled dataset. For live summaries, the selected registered classifier predicts one of its trained categories. That predicted category is an application inference and is stored as a Kafka-origin Prediction, separate from the upstream sections.

## Kafka stages and reliability

The backend creates the eight configured topics with three partitions and replication factor one for local development. `news.raw` events are size-checked and restricted to HTTPS BBC hosts. The raw consumer cleans text, emits a preprocessed event and a classification request. The classifier loads the currently active model artifact and emits probabilities, confidence, latency, content hash and model version. The results consumer stores predictions with the event ID as a unique key, making result replay idempotent.

Consumers disable automatic offset commits. A successfully handled event is committed after downstream acknowledgments; a rejected/unprocessable payload goes to a dead-letter topic and is then committed. If dead-letter delivery itself fails, the source offset remains uncommitted. Local topic replication is one, so this setup is for development and does not provide broker fault tolerance.

## Background work

Django API requests enqueue model training and Spark MLlib LDA through Celery/Redis. The model training workflow stores metrics and a joblib artifact; the user registers a successful experiment and explicitly activates a version. Predictions use that active version. The app defaults to SQLite for a low-friction local start; PostgreSQL is available in Compose for a more representative multi-process database setup.
