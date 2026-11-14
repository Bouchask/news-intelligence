# Initial architecture decisions

1. **Reuse the installed Spark distribution.** The host has Spark 4.2.0, so the project must verify that version's PySpark APIs instead of installing Spark 3 over it. The Spark runner bundles PySpark libraries; ordinary Python interpreters cannot currently import them.
2. **Use Python 3.12 for the application environment.** Python 3.12 is installed alongside 3.14 and provides a wider compatibility window for Django and scientific Python dependencies.
3. **Keep corpus inspection independent of Spark.** Dataset format detection and stable IDs use the Python standard library, so the input can be validated before starting a Spark job. Distributed summaries are provided through the Spark SQL module.
4. **Use SQLite as the initial API default and PostgreSQL through configuration.** This lets the API shell start locally without assuming that a PostgreSQL server is running. `DATABASE_URL` switches to PostgreSQL.
5. **Never populate dashboard metrics with examples.** The initial dashboard explicitly shows unconfigured states until the API and a real dataset provide values.
6. **Keep historical and current data separate.** The archived BBC corpus is a static, non-commercial research dataset. Current headline summaries are fetched separately from the configured third-party API, deduplicated by article URL, and never used as the archive's five training labels.

## Initial project stages

- Foundation: monorepo, Django API shell, health endpoint, frontend shell.
- Dataset: CSV/category-folder discovery, stable IDs, real corpus summary, Spark EDA entry point.
- Later stages: Spark NLP/ML, experiment registry, Kafka streaming, broader API integration, infrastructure and deployment.
