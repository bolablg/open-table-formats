# Local table metadata lab

Compare the table state recorded by Apache Iceberg, Delta Lake and Apache Hudi after changes to the same Olist orders. The lab preserves the eight native source fields and checks all business values, including nullable timestamps, after each operation.

## Choose a notebook

| Path | Operations | Default row counts | Results |
| --- | --- | --- | --- |
| [Manual notebook](notebooks/Olist_Table_Formats_Manual.ipynb) | Create, insert, update, delete | 3 → 5 → 5 → 4 | SQL, DataFrame writes and metadata inspection directly in cells |
| [Automated notebook](notebooks/Olist_Table_Formats.ipynb) | Create, insert, delete | 3 → 5 → 4 | Shared runner, validation and saved explorer snapshots |

Both let you configure initial rows, inserts, deletes and sample seed. The manual path adds a one-day change to one estimated delivery date. Follow the [manual guide](docs/manual-walkthrough.md) or [automated guide](docs/olist-walkthrough.md).

## Start

Requirements: Docker Engine/Desktop with Compose v2, host Python 3.9+, several GB for images, and enough Docker memory for a 2 GB Spark driver. Download the source CSV using the [data instructions](../DATA_LICENSE.md).

Run from this `local-lab/` directory:

```sh
export OLIST_SOURCE_CSV='/absolute/path/to/olist_orders_dataset.csv'
make -f Makefile.olist build
make -f Makefile.olist notebook
```

Open the token-bearing Jupyter URL printed in the logs. Choose a notebook, edit `CONFIG`, and run cells in order using a fresh kernel. Run one lab writer at a time. The CSV is mounted read-only.

For headless execution:

```sh
make -f Makefile.olist execute
make -f Makefile.olist manual-execute
```

These are alternative notebook paths. Their executed outputs are saved under `evidence/olist/` and `evidence/olist/manual/executions/`, respectively.

## Explorer and CLI

Start the explorer in another terminal:

```sh
make -f Makefile.olist explorer
```

Open http://127.0.0.1:8765 and select **Refresh evidence** after an automated stage. Compare rows, row changes, schemas, metadata and file changes. The explorer reads saved automated snapshots; inspect manual outputs in the manual notebook.

The automated stages can also be run separately:

```sh
make -f Makefile.olist start
make -f Makefile.olist new INITIAL_ROWS=4 INSERT_ROWS=3 DELETE_ROWS=2 SAMPLE_SEED=reader-example-v1
make -f Makefile.olist create
make -f Makefile.olist insert
make -f Makefile.olist delete
```

This configuration gives **4 → 7 → 5** rows. Later stages use the run's saved configuration.

## Storage

Every launch uses Compose project `open-table-formats-lab`, network `open-table-formats-lab_default`, and volume `open-table-formats-lab_s3-data`. Keep that project name when moving the checkout to reuse storage. Two checkouts with the same project name address the same services and volume, so run only one at a time.

Olist runs use separate object prefixes and local evidence directories. Use the [scoped reset](docs/olist-walkthrough.md#scoped-reset-and-stopping) to remove one run's table objects. The base Makefile's `make reset` deletes the shared S3 volume and should not be used for Olist runs.

Source data, generated outputs and credentials are excluded from Git. Keep dataset-derived records local and clear notebook outputs before sharing source notebooks.

## Validation

```sh
make -f Makefile.olist test
python3 scripts/compose_lab.py run --rm olist python /workspace/tests/check_reader_commands.py
python3 scripts/compose_lab.py run --rm olist python /workspace/tests/check_configurations.py
```

Optional browser checks require host Playwright and Chromium: `python3 tests/ui_smoke.py` and `python3 tests/notebook_ui.py`.

## Architecture and limits

![Local CSV input, Spark, three independent tables and a saved-snapshot explorer.](docs/assets/local-architecture.png)

[Editable SVG](docs/assets/local-architecture.svg) · [High-resolution PNG](docs/assets/local-architecture.png) · [Alt text](docs/assets/local-architecture.alt.txt)

Pinned runtime: Spark 3.5.7, Scala 2.12, Java 17, Iceberg 1.11.0, Delta 3.3.2, Hudi 1.2.0, Hadoop AWS 3.3.4, LocalStack 4.8.1, JupyterLab 4.4.10 and nbconvert 7.16.6.

The lab checks sequential correctness and metadata. It does not test performance, concurrent writers, crash recovery or cloud interoperability.

The base `Makefile`, synthetic generator and [synthetic exercise](docs/architecture.md) provide a separate 100-row sequence with create, insert, update, delete and schema evolution. That exercise uses a different schema from the Olist notebooks.
