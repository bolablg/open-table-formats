# Olist metadata: configurable counts, defaults 3 → 5 → 4

**How do Iceberg, Delta Lake and Hudi record the same table changes?**

The central walkthrough is [Olist_Table_Formats.ipynb](../notebooks/Olist_Table_Formats.ipynb). It exposes exactly three operations with configurable counts and seed: create initial real orders, insert distinct reserved orders, then delete deterministic targets. Defaults are 3 initial, 2 inserts and 1 deletion, giving 3 → 5 → 4. All three formats must return the same business values after every step. There is no update or schema-evolution commit before the core delete.

The companion [local explorer](http://127.0.0.1:8765) reads these generated snapshots. Its main page displays configured runs, expected counts and sample seed. The [earlier runs view](http://127.0.0.1:8765/legacy) lets you inspect saved results from other workflows.

For visible cell-by-cell create/insert/update/delete, use the separate [manual notebook guide](manual-walkthrough.md), default **3 → 5 → 5 → 4**. This automated core remains **3 → 5 → 4**.

## Source and license

Download the **Brazilian E-Commerce Public Dataset by Olist** from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), then locate `olist_orders_dataset.csv`. Kaggle lists **CC BY-NC-SA 4.0**: attribution, noncommercial and share-alike conditions apply. See the [license](https://creativecommons.org/licenses/by-nc-sa/4.0/). Obtain the source directly; this project does not bundle or redistribute it.

The locally verified source has 99,441 rows and SHA-256:

```text
8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf
```

Each run records the actual source and sample checksums, seed, configuration, selected ranks, stage order and expected counts. The whole CSV is validated; only the configured initial-plus-insert sample enters this metadata walkthrough (five orders by default). Changing the source during a run stops further writes. Generated evidence contains source-derived rows: keep it local and clear outputs before sharing notebooks. Ignore rules exclude generated evidence.

## Native input and deterministic selection

| Fields | Type | Required in source validation |
| --- | --- | --- |
| `order_id`, `customer_id`, `order_status` | string | yes |
| `order_purchase_timestamp`, `order_estimated_delivery_date` | timestamp | yes |
| `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date` | nullable timestamp | no |

Headers must exactly match these eight native fields. Duplicate keys, missing required values and invalid nonblank timestamps are rejected. Empty lifecycle values remain null. Keys stay strings. No product, country, cost, quantity or channel fields are invented.

Sort source orders by `(SHA256(UTF-8 sample_seed + ":" + order_id), order_id)`. The first `initial_rows` ranks form the initial table; the next `insert_rows` are distinct reserved inserts. Delete targets start at rank 2 and wrap through the selected ranks until `delete_rows` distinct targets are selected. Defaults select ranks **1–3** initially, insert ranks **4–5** and delete **rank 2**. Selection does not depend on CSV row order.

Initial size must be a positive integer. Insert/delete counts must be nonnegative integers, deletion cannot exceed initial plus inserted rows, and the source must contain enough unique orders. The seed must be a nonblank string. Zero inserts/deletes are explicit no-op stages: the state is still validated and captured, without a table write. Deleting every selected row is supported.

Timestamp text uses `yyyy-MM-dd HH:mm:ss` without an offset. UTC is the declared parsing/display convention for this experiment, **not verified source timezone provenance**. The original source CSV is unchanged. Deletion is a controlled demonstration, not a claim about Olist's real history.

## Setup and launch

Requirements: Docker with Compose v2, Python 3.9+ for the explorer, and memory for a 2 GB Spark driver. The image pins Spark 3.5.7, Iceberg 1.11.0, Delta Lake 3.3.2 and Hudi 1.2.0, with JupyterLab 4.4.10 and nbconvert 7.16.6. No host Spark or Java installation is needed.

From the repository’s `local-lab/` directory:

```sh
export OLIST_SOURCE_CSV='/absolute/path/to/olist_orders_dataset.csv'
make -f Makefile.olist build
make -f Makefile.olist notebook
```

Open the token-bearing localhost URL printed in the notebook logs, then open `notebooks/Olist_Table_Formats.ipynb`. Its published port is `127.0.0.1:8888`. Edit the single `CONFIG` cell to explore other values, then execute cells in order. Later cells derive all expected values from that configuration. The source bind mount is read-only. Setup starts the local S3 emulator and creates the bucket if needed; it does not seed or reset the synthetic warehouse.

In another terminal from the same project directory:

```sh
python3 scripts/explore_evidence.py --port 8765
```

Open **http://127.0.0.1:8765**. Press **Refresh evidence** after each operation. The main page selects the current run's latest completed stage. The three stage choices include their actual expected row counts. Run IDs include `olist_article_<initial>_<insert>_<delete>_`; manifests and snapshots record all counts, seed, expected progression and actual target ranks.

## The three visible operations (default configuration)

| Stage | Controlled operation | Expected rows per format |
| --- | --- | ---: |
| Create | Create independent tables from ranks 1–3 | 3 |
| Insert | Add source ranks 4–5, with no overlap | 5 |
| Delete | Remove rank 2; no intervening update/evolution | 4 |

Tables remain unpartitioned. Iceberg uses format version 2 and copy-on-write row changes. Hudi uses Copy-on-Write, nonpartitioned string keys and commit-time ordering. Sampling is configurable; format settings are not selectively altered to make any metadata look cheaper. Output file counts are observed results, not fixed expectations.

Every stage compares **every business value** against an independent expected state, including keys, nulls and timestamps. Hudi's internal columns are excluded from that business comparison. Each snapshot captures actual rows, schema, row differences, metadata interfaces, raw previews, full object inventory and file changes.

Read business rows first, then metadata, then physical file changes. Iceberg snapshots select manifest lists and manifests; Delta publishes log actions; Hudi completed commits describe file-group changes. Logical deletion can replace a file while older physical files remain. Physical inventory is not the active file set or a performance ranking.

The explorer provides **Rows**, **Row changes**, **Schema**, **Metadata** and **File changes**, with stage/format selection, comparison and downloads. It labels pending, failed, stalled and reset runs. Hudi's main timeline and business-table logs are separated from its auxiliary metadata table under `.hoodie/metadata/`. Auxiliary logs do not make the business table Merge-on-Read.

Actual text is displayed directly; captured Avro/Parquet metadata is decoded. Inline limits are twelve files, 300 KB per file and 100 decoded records. Large metadata integers are decimal strings in the browser/API/downloads to preserve every digit; original captured JSON retains numeric types.

## Reproduce and inspect evidence

Execute the same notebook headlessly:

```sh
make -f Makefile.olist execute
```

The latest executed output is `evidence/olist/executed-tiny-walkthrough.ipynb`. Each completed execution is also retained at `evidence/olist/runs/<run_id>/executed-notebook.ipynb`.

Alternatively, invoke the same API through separate CLI stages:

```sh
make -f Makefile.olist start
make -f Makefile.olist new
make -f Makefile.olist create
make -f Makefile.olist insert
make -f Makefile.olist delete
```

Change all four values in the notebook configuration cell:

```python
CONFIG = {"initial_rows": 3, "insert_rows": 2, "delete_rows": 1,
          "sample_seed": "open-table-formats-lab-v1"}
lab = OlistLab.start(**CONFIG)
```

The same parameters are available through the CLI. For example, 4 initial, 3 inserts and 2 deletions produce **4 → 7 → 5**:

```sh
make -f Makefile.olist new INITIAL_ROWS=4 INSERT_ROWS=3 DELETE_ROWS=2 SAMPLE_SEED=reader-example-v1
make -f Makefile.olist create
make -f Makefile.olist insert
make -f Makefile.olist delete
```

Direct CLI initialization is equivalent:

```sh
docker compose -p open-table-formats-lab -f docker-compose.yml -f docker-compose.olist.yml run --rm olist python /workspace/scripts/olist_stage.py new --initial-rows 4 --insert-rows 3 --delete-rows 2 --sample-seed reader-example-v1
```

Configuration flags belong to `new`; later stages use its saved manifest and reject configuration overrides. Starting another configuration always creates a new isolated run.

Repeated, unsupported and out-of-order stages are rejected. After a failed operation, start a fresh run because some formats may have committed before failure. Use the manual notebook for updates. The separate synthetic exercise includes schema evolution.

Table objects are under `s3a://lakehouse-lab/olist/runs/<run_id>/`; evidence is under `evidence/olist/runs/<run_id>/`. The optional synthetic exercise uses separate generated data. Source-derived rows and generated evidence stay local.

Focused checks:

```sh
make -f Makefile.olist test
docker compose -p open-table-formats-lab -f docker-compose.yml -f docker-compose.olist.yml run --rm olist python /workspace/tests/check_reader_commands.py
docker compose -p open-table-formats-lab -f docker-compose.yml -f docker-compose.olist.yml run --rm olist python /workspace/tests/check_scoped_reset.py
```

Optional host Playwright checks: `python3 tests/ui_smoke.py --url http://127.0.0.1:8765` and `python3 tests/notebook_ui.py`. Reports and screenshots are stored under `evidence/olist/checks/<run_id>/`.

## Scoped reset and stopping

A fresh execution needs no deletion. To delete only one run's disposable table objects while retaining its evidence:

```sh
make -f Makefile.olist reset RUN_ID=olist_article_3_2_1_YYYYMMDDTHHMMSSZ_abcdefgh
```

Use its actual run ID. Reset requires exact confirmation and restricts deletion to that run's prefix. The retained manifest is marked `reset`. Earlier runs are read-only. Never use the synthetic `make reset`: it deletes the shared S3 volume.

Stop the notebook without removing storage:

```sh
docker compose -p open-table-formats-lab -f docker-compose.yml -f docker-compose.olist.yml stop notebook
```

Stop the explorer with Ctrl-C in its terminal.

## Scope

This metadata walkthrough verifies sequential correctness on one pinned Spark stack. It does not establish production performance, concurrency, crash recovery, streaming ingestion, maintenance costs or cross-engine interoperability.

All launch paths pin `-p open-table-formats-lab`. Preserve that name to reuse the existing network and S3 volume. Temporary CLI containers remain enabled. See [repository data instructions](../../DATA_LICENSE.md).

Primary references: [Spark CSV options](https://spark.apache.org/docs/3.5.7/sql-data-sources-csv.html), [Iceberg metadata specification](https://iceberg.apache.org/spec/), [Delta protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md), [Hudi timeline](https://hudi.apache.org/docs/timeline/).
