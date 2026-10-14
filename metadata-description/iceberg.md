# Apache Iceberg: snapshots and file references

[Back to the guide index](README.md)

The reference run ends with **4 rows in 4 active data files**, selected by snapshot `5484902428416146878`. Its physical inventory contains **5 Parquet files** because an older file remains stored. This guide describes Iceberg **1.11.0, table format v2**, not every possible Iceberg layout.

## Read the files in this order

```text
Hadoop catalog table resolution in this lab
  → metadata/v3.metadata.json
    → current-snapshot-id selects a snapshot
      → snapshot's manifest-list (.avro)
        → manifest files (.avro)
          → active data files (.parquet)
```

Snapshots are embedded in the metadata JSON. The manifest list and manifests are separate Avro files. The JSON does not directly enumerate the Parquet filenames. A reader follows these references rather than treating a directory listing as the table. [1]

## Latest metadata and system file map

All paths below are under the table's `metadata/` directory.

| File | Role and observed contents |
| --- | --- |
| `v3.metadata.json` | Latest saved table metadata. Contains schema 0, partition spec 0, the current snapshot pointer, three snapshots and previous metadata references. |
| `version-hint.text` | Contains `3`. A version-discovery hint used by this lab's Hadoop catalog implementation, not a snapshot ID or a universal Iceberg catalog file. [2] |
| `snap-5484902428416146878-1-aed271a5-0ade-4677-b553-70d274103627.avro` | Current snapshot's manifest list. Contains three manifest records. |
| `aed271a5-0ade-4677-b553-70d274103627-m1.avro` | New manifest with one added data file containing one row. |
| `aed271a5-0ade-4677-b553-70d274103627-m0.avro` | Rewritten manifest with one existing file containing one row, plus one deleted entry for the old two-row file. |
| `e5994a38-6f82-4e0e-948c-e11bba1c7f27-m0.avro` | Reused insert-stage manifest with two added files containing two rows in total. Its entry statuses describe the manifest's original changes, not two new additions by the delete. |

The retained inventory also includes `v1.metadata.json`, `v2.metadata.json`, the two earlier `snap-*.avro` manifest lists and `98e0f66a-ad0a-4233-a7b1-cd7bfea963a7-m0.avro`. These preserve earlier state; they are not all part of the current read plan. The saved raw viewer decoded all 11 eligible metadata objects.

## Interpret `v3.metadata.json`

| Field or group | Meaning in this run |
| --- | --- |
| `format-version: 2` | Table specification version, distinct from library version 1.11.0. |
| `table-uuid` | Stable table identity. |
| `location` | Base storage path ending in `/iceberg/lab/orders`. |
| `last-sequence-number: 3` | Highest assigned snapshot sequence number. |
| `last-updated-ms: 1791279029768` | Metadata update time: 2026-10-06 09:30:29.768 UTC. |
| `last-column-id: 8` | Highest assigned column ID, not a general-purpose column count. |
| `current-schema-id: 0`, `schemas` | Select the eight-column schema described below. |
| `default-spec-id: 0`, `partition-specs` | The selected spec has no partition fields: this table is unpartitioned. |
| `last-partition-id: 999` | Partition-field ID bookkeeping, not 999 partitions. |
| `default-sort-order-id: 0`, `sort-orders` | No declared sort order. |
| `properties` | Copy-on-write update/delete modes, Parquet Zstandard compression and the label `owner: spark`. The owner label alone is not an access-control policy. |
| `current-snapshot-id`, `refs.main` | Both select snapshot `5484902428416146878`. |
| `snapshots` | Three saved snapshots with parent links, sequence numbers, timestamps, summaries, schema IDs and manifest-list paths. |
| `snapshot-log` | Changes to the current snapshot. |
| `metadata-log` | Previous metadata JSON references: v1 and v2, not a separate list of data commits. |
| `statistics`, `partition-statistics` | Empty lists of separately registered statistics files. File-level statistics still exist in manifests. |

Snapshot IDs are opaque identifiers. Use sequence numbers and parent links for this history, not numeric sorting of IDs. Preserve IDs as 64-bit integers or strings in tools; ordinary JavaScript numbers cannot represent these IDs exactly. [1]

### Schema

| Field ID | Column | Type | Nullable |
| --- | --- | --- | --- |
| 1 | `order_id` | string | Yes |
| 2 | `customer_id` | string | Yes |
| 3 | `order_status` | string | Yes |
| 4 | `order_purchase_timestamp` | timestamptz | Yes |
| 5 | `order_approved_at` | timestamptz | Yes |
| 6 | `order_delivered_carrier_date` | timestamptz | Yes |
| 7 | `order_delivered_customer_date` | timestamptz | Yes |
| 8 | `order_estimated_delivery_date` | timestamptz | Yes |

`required: false` permits nulls. `order_id` is not a primary-key declaration. Field IDs preserve column identity independently of names or positions. `timestamptz` represents an instant, not the original named time zone; the lab's UTC parsing convention does not establish the source dataset's original time zone. [1]

## Interpret the three snapshots

| Sequence | Operation | Added files / records | Removed files / records | Active files / records | Active bytes |
| --- | --- | --- | --- | --- | ---: |
| 1 | append | 2 / 3 | 0 / 0 | 2 / 3 | 6,124 |
| 2 | append | 2 / 2 | 0 / 0 | 4 / 5 | 12,247 |
| 3 | overwrite | 1 / 1 | 1 / 2 | 4 / 4 | 12,288 |

The SQL DELETE removed one business row. Copy-on-write replaced the affected two-row file with a one-row survivor file. Therefore `deleted-records: 2` and `added-records: 1` are not two logical deletions and a new business insertion:

```text
Rows:         5 - 2 + 1 = 4
Active files: 4 - 1 + 1 = 4
Active bytes: 12,247 - 3,063 + 3,104 = 12,288
```

`operation: overwrite` describes this file replacement. Delete-file, position-delete and equality-delete counters are all zero. `changed-partition-count: 1` refers to the single unpartitioned group. Manifest creation/reuse counters concern metadata files, not Parquet counts. Engine/application fields identify the writer, not a performance guarantee.

## Manifest-list and manifest fields

The current manifest list has three records. Each includes `manifest_path`, `manifest_length`, `partition_spec_id`, `content`, snapshot/sequence identifiers, file/row counters and `partitions`. `content: 0` identifies data manifests. Empty partition summaries are expected here.

Within a manifest, each entry has `status` (`0` existing, `1` added, `2` deleted), snapshot/sequence identifiers and a `data_file` structure. Null entry sequence numbers can inherit manifest-level sequence information; they are not automatically corrupt records. [1]

Important `data_file` fields:

- `file_path`, `file_format`, `file_size_in_bytes`, `record_count`: the object and its physical row count.
- `partition`, `sort_order_id`: layout information; empty partition data and sort order 0 here.
- `column_sizes`, `value_counts`, `null_value_counts`, `nan_value_counts`: metrics keyed by schema field ID.
- `lower_bounds`, `upper_bounds`: typed, potentially truncated bounds, not necessarily exact minimum/maximum business values. The raw Avro viewer can render binary bounds awkwardly; prefer decoded `readable_metrics` in the SQL files view.
- `split_offsets`: offsets used for splitting reads, not row IDs.
- `key_metadata`, `equality_ids`, `referenced_data_file`: optional fields unused in these data-file records.

Some nullable columns in SQL metadata views belong to broader reader schemas and do not imply those optional features are active in this v2 table.

## SQL metadata tables are views, not extra files

The adapter captures these views for `<table>` in its configured catalog: [3]

| View | What the saved result shows |
| --- | --- |
| `<table>.history` | Three current-snapshot transitions; all are current ancestors. |
| `<table>.snapshots` | Three snapshot records and their summaries. |
| `<table>.manifests` | Three manifests referenced by the current snapshot. |
| `<table>.files` | Four active data files; `record_count` sums to four. |

Use the notebook's configured table identifier to inspect them, for example `lab.spark.table(f"{table}.files").show(truncate=False)`. These are read-only inspection calls; they require the catalog and referenced objects to remain available.

## Limits and sources

The saved inventory shows no physical file removals during this delete. That is compatible with logical removal from the current snapshot. Historical reads require retained, accessible files; this JSON alone does not prove their present availability. These counts are not a benchmark.

1. [Iceberg specification: metadata, manifests and metrics](https://iceberg.apache.org/spec/)
2. [Iceberg 1.11.0 HadoopTableOperations implementation](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/hadoop/HadoopTableOperations.java)
3. [Iceberg 1.11.0 Spark metadata queries](https://iceberg.apache.org/docs/1.11.0/spark-queries/)
4. [Lab metadata inspector](../local-lab/scripts/format_adapters.py) and [Olist configuration](../local-lab/scripts/olist_adapters.py)
