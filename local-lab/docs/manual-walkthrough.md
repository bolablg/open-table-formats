# Manual and automated Olist notebooks

Both notebooks use the downloaded source CSV read-only and the pinned local Docker stack. They answer different teaching needs.

| Path | Operations | Default rows | Implementation |
| --- | --- | --- | --- |
| [Automated notebook](../notebooks/Olist_Table_Formats.ipynb) | Create, insert, delete | 3 → 5 → 4 | Shared runner/adapters and explorer snapshots |
| [Manual notebook](../notebooks/Olist_Table_Formats_Manual.ipynb) | Create, insert, update, delete | 3 → 5 → 5 → 4 | Self-contained visible SQL/DataFrame writes and metadata queries |

## Open the manual notebook

From the repository's `local-lab/` directory:

```sh
export OLIST_SOURCE_CSV='/absolute/path/to/olist_orders_dataset.csv'
make -f Makefile.olist notebook
```

Authenticate with the token-bearing Jupyter URL in the logs, then open:
http://127.0.0.1:8888/lab/tree/notebooks/Olist_Table_Formats_Manual.ipynb

Use a fresh kernel. Edit the four `CONFIG` values, then run cells in order. Do not run another lab writer at the same time. All business writes and metadata reads appear directly in cells. The four small in-notebook utilities show Spark configuration, S3 listing, bounded actual metadata decoding, and independent equality checks. No project runner, adapter, helper import or script invocation is used.

The notebook creates and inspects Iceberg first, then Delta, then Hudi. It subsequently inserts, updates and deletes in each format. The single update shifts the first initial order's estimated delivery date by one day without changing row count. Inserts use distinct reserved real source rows; update/delete behavior is a simulation. Optional timestamp nulls remain null. UTC is an explicit lab parsing convention, not verified source timezone provenance.

## Separate Spark contexts

Iceberg uses a named Hadoop catalog. Delta configures `spark_catalog` as `DeltaCatalog`; Hudi configures it as `HoodieCatalog` and uses its own SQL extension/Kryo registrator. The manual notebook stops each Spark context before opening the next rather than claiming both catalog values coexist. It records the actual extension/catalog settings for all twelve format/stage sessions. The automated notebook uses its own DataSource and SQL configuration.

## Evidence and safeguards

Every run has a new `s3a://lakehouse-lab/olist/manual/<run_id>/` prefix and local `evidence/olist/manual/<run_id>/` directory. Creates refuse existing table paths, stage guards reject replay within the kernel, and source checksums are checked before and after writes. No global reset, source write, automated current-selector update or cloud endpoint is used.

Actual Iceberg metadata JSON and decoded manifest-list Avro, raw Delta commit JSON, and Hudi properties/completed-commit metadata appear after each operation. Hudi's business timeline and auxiliary metadata-table log files are counted separately. Metadata previews are bounded at 1 MB and 20 Avro records and report truncation. These outputs contain source-derived data and remain local.

Headless execution uses the same cells:

```sh
make -f Makefile.olist manual-execute
```

The executed notebook gets a unique filename under ignored `evidence/olist/manual/executions/`. Its final output gives the manual run ID and verification path. The source notebook is output-free. The explorer at http://127.0.0.1:8765 continues to read saved **automated** snapshots, not live tables or the manual artifacts.

## Local architecture figure

![Local table formats architecture](assets/local-architecture.png)

[Editable SVG](assets/local-architecture.svg) · [4320 × 2400 PNG](assets/local-architecture.png) · [Alt text](assets/local-architecture.alt.txt)

The figure is grounded in the actual Compose services: Jupyter/Spark and temporary `olist` jobs, LocalStack's S3 API (`s3`), and its persistent `s3-data` volume. Each format owns separate table data and metadata. Dashed arrows show saved automated evidence flowing to the host Python explorer. It depicts no AWS cloud infrastructure or Glue catalog.
