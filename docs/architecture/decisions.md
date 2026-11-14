# Initial architecture decisions

1. **Use the pinned PySpark distribution in the project environment.** The project environment pins PySpark 4.2.0, matching the host Spark release observed during the initial audit. Spark jobs read data to DataFrames directly; they do not first load the full corpus into driver-side Python objects. Java 17 or later is required.
2. **Use Python 3.12 for the application environment.** Python 3.12 is installed alongside 3.14 and provides a wider compatibility window for Django and scientific Python dependencies.
3. **Keep corpus inspection independent of Spark.** Dataset format detection and stable IDs use the Python standard library, so the input can be validated before starting a Spark job. Distributed summaries are provided through the Spark SQL module.
4. **Use SQLite as the initial API default and PostgreSQL through configuration.** This lets the API shell start locally without assuming that a PostgreSQL server is running. `DATABASE_URL` switches to PostgreSQL.
5. **Never populate dashboard metrics with examples.** The initial dashboard explicitly shows unconfigured states until the API and a real dataset provide values.
6. **Keep historical and current data separate.** The archived BBC corpus is a static, non-commercial research dataset. Current headline summaries are fetched separately from the configured third-party API, deduplicated by article URL, and never used as the archive's five training labels.

## Initial project stages

- Foundation: monorepo, Django API shell, health endpoint, frontend shell.
- Dataset: CSV/category-folder discovery, stable IDs, corpus summaries, and Spark DataFrame readers.
- ML: Spark SQL EDA, MLlib Naive Bayes with stratified CV and held-out metrics, MLlib LDA with Parquet topic distributions, and scikit-learn comparison models.
- Backend/dashboard: asynchronous experiment/topic jobs, registered model serving, live BBC metadata import, Kafka replay and prediction consumers.
- Runtime caveat: local sandbox denied Java's Py4J socket bind during Spark smoke run; a normal host shell with local socket access is needed to verify actual Spark execution.
