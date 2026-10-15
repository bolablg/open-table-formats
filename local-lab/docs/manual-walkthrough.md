# A manual notebook, from scratch

The [manual notebook](../notebooks/Olist_Table_Formats_Manual.ipynb) contains the complete exercise. It imports standard Python modules and PySpark, starts one Spark session, and runs each table operation directly in visible cells. There are no project imports, helper-function definitions, script calls, adapter classes or explorer snapshots.

## What you will do

1. Choose a CSV path and a local output directory.
2. Start Spark with the pinned format libraries.
3. Select real source orders and state the expected results.
4. Work through Iceberg: create, insert, update, delete, then open metadata.
5. Repeat the same sequence for Delta and Hudi.
6. Compare all business values and confirm the source CSV is unchanged.

Defaults are **3 → 5 → 5 → 4** for each format. The one-day estimated-delivery update and deletion are controlled teaching examples. The notebook validates the selected sample, not the entire source dataset. UTC is a parsing convention, not verified source time-zone provenance.

## Run without this repository's infrastructure

You can copy just the notebook to your own folder. You need:

- Python 3.10 or 3.11 and Java 17.
- PySpark 3.5.7 and Jupyter, for example `pip install pyspark==3.5.7 jupyterlab` in an environment you choose.
- The separately downloaded `olist_orders_dataset.csv`. See [data acquisition and license](../../DATA_LICENSE.md).
- Internet access for the first Maven dependency download, unless the matching JARs are already installed.

Open Jupyter, create a fresh Python kernel and edit `CSV_PATH` in the first code cell. The remaining cells run in order. `INITIAL_ROWS`, `INSERT_ROWS`, `DELETE_ROWS` and `SAMPLE_SEED` are also visible there.

The setup cell shows all Spark configuration. It uses Spark 3.5 / Scala 2.12 artifacts for Iceberg 1.11.0, Delta Lake 3.3.2 and Hudi 1.2.0. It detects the existing lab image's bundled JARs; otherwise Spark resolves the listed Maven coordinates. The standalone Maven-download path is documented separately from the bundled runtime used for local verification.

This is an **open-source Spark** recipe, not a Databricks Runtime installation recipe. No Databricks account, cloud catalog, LocalStack, S3 bucket, explorer server or project Python module is required.

## Optional: use the existing Docker runtime

From `local-lab/`, set `OLIST_SOURCE_CSV` to the downloaded orders CSV. Build the runtime images first if needed:

```sh
make -f Makefile.olist build
make -f Makefile.olist manual-notebook
```

The manual launch skips the LocalStack dependency. Open the token-bearing Jupyter URL printed in the logs, then select `notebooks/Olist_Table_Formats_Manual.ipynb`. The CSV is mounted read-only at `/source/olist_orders_dataset.csv`.

For notebook execution without the Jupyter UI:

```sh
make -f Makefile.olist manual-execute
```

This optional wrapper executes the notebook's own cells, not a project runner. It skips LocalStack and mounts a local output folder. Executed notebooks stay under ignored `evidence/olist/manual/executions/`; table files from that wrapper stay under ignored `evidence/olist/manual/local-tables/`.

## Why one session works here

Iceberg has a named Hadoop catalog. Delta owns the Spark session catalog. Hudi uses its DataFrame writer/reader, not Hudi SQL, so it does not need to replace Delta's session catalog. Hudi's Kryo serializer/registrator and Iceberg/Delta extensions are explicit startup settings.

This combination is verified on the bundled local stack. Other Spark, Scala or format versions require compatibility checks. A fresh kernel matters because startup extensions and serializer settings cannot be reliably replaced after a Spark context exists.

## Inspect the metadata, without a decoder script

- Iceberg: SQL metadata views, the actual versioned JSON and the current snapshot's decoded Avro manifest list.
- Delta: SQL history and the actual latest JSON Lines commit.
- Hudi: the actual table properties, timeline filenames and decoded Avro completed commit.

The Avro cells use the Java Avro library already available to Spark. They are written directly in the notebook. The small exercise prints complete records; it is not a bounded metadata browser for production-sized tables.

Each operation compares every native business value with expectations derived before any table write. Hudi metadata columns are excluded from those business comparisons.

## Outputs and safeguards

`RUN_DIR` is a new UUID directory under the configurable local `OUTPUT_BASE`. Creates refuse existing table paths. The notebook never resets earlier runs or modifies the automated current-run pointer. It includes no cleanup command.

The default `manual-output/` is relative to the notebook process's working directory, not necessarily the notebook file. On your own computer it is ordinary local disk. In the optional interactive Docker runtime it is container-local unless you choose a mounted path, such as `/workspace/evidence/olist/manual/tables`. The headless Makefile wrapper mounts its output directory automatically.

Restart the kernel and start a fresh run after a failure or before replaying mutations. Run only one memory-intensive lab execution at a time. Keep CSV files, generated tables and executed notebook outputs local; public source notebooks must have cleared outputs.

## Separate from the automated lab

The [automated notebook](../notebooks/Olist_Table_Formats.ipynb) still uses shared scripts, LocalStack and saved explorer snapshots: **3 → 5 → 4**. Those files are unchanged by the manual rewrite. The explorer reads automated evidence, not this manual notebook's local tables.

The manual exercise tests sequential business-value correctness and demonstrates metadata. It is not a benchmark, concurrency test, crash-recovery test or cross-engine interoperability test.
