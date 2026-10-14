# Delta Lake: a transaction log of actions

[Back to the guide index](README.md)

For every captured property, grouped by importance, see the [complete field reference](delta-field-reference.md).

The reference run ends at **table version 2**, with **4 active Parquet files and 4 business rows**. The latest commit is a DELETE. This guide describes Delta Lake **3.3.2**, with reader protocol 1 and writer protocol 2.

## Latest metadata and system file map

| File under `_delta_log/` | Role in the captured run |
| --- | --- |
| `00000000000000000002.json` | Latest commit: one `commitInfo`, one `remove` and one `add` action. |
| `00000000000000000002.crc` | Version checksum JSON: four active files, 12,443 active bytes and retained metadata/protocol summaries. |
| `00000000000000000001.json` | Insert commit: two `add` actions and a `commitInfo`. |
| `00000000000000000000.json` | Initial write: two `add` actions, `metaData`, `protocol` and `commitInfo`. |
| `00000000000000000000.crc`, `00000000000000000001.crc` | Earlier version checksum files. |

All six commit/checksum objects were captured as text. No checkpoint, `_last_checkpoint`, sidecar, change-data or deletion-vector file appears in the saved inventory. The physical table folder contains five Parquet objects, including the old file removed from the active state.

## How a reader reconstructs version 2

```text
Version 0: schema + protocol + initial active files
  → version 1: add the insert files
    → version 2: remove the old file, add its replacement
      → four active data files
```

A Delta commit is newline-delimited JSON: each line is a separate action object. It is not one JSON array. The latest commit describes changes, not the entire table. The schema and protocol remain effective from version 0 because later commits do not replace them. Longer histories can use checkpoints plus subsequent commits. [1]

## Interpret the latest DELETE

The following is a selected, structurally abbreviated excerpt. Placeholder filenames replace generated paths; this is not a raw commit export.

```json
{"commitInfo":{"operation":"DELETE","readVersion":1,"isolationLevel":"Serializable","isBlindAppend":false,"operationMetrics":{"numDeletedRows":"1","numCopiedRows":"1","numAddedFiles":"1","numRemovedFiles":"1"}}}
{"remove":{"path":"old-two-row-file.parquet","dataChange":true,"extendedFileMetadata":true,"partitionValues":{},"size":2873}}
{"add":{"path":"replacement-one-row-file.parquet","partitionValues":{},"size":3111,"dataChange":true}}
```

The affected file held two orders. Delta removes that file from the active set and writes the surviving order to a replacement file:

```text
Rows:         5 - 1 deleted business row = 4
Active files: 4 - 1 + 1 = 4
Active bytes: 12,205 - 2,873 + 3,111 = 12,443
```

`numCopiedRows: 1` means one survivor was rewritten, not one new business order. All deletion-vector counters are zero; this delete used a file rewrite. `numAddedChangeFiles: 0` means this operation did not generate separate change-data files.

### `commitInfo`: operation provenance

| Field | Interpretation |
| --- | --- |
| `timestamp` | Recorded commit time; latest raw value `1791279033859`. |
| `operation`, `operationParameters` | DELETE and its predicate. The predicate contains Spark expression details, not a portable query API. |
| `readVersion: 1` | The transaction read table version 1. |
| `isolationLevel: Serializable` | The isolation level reported for this commit. |
| `isBlindAppend: false` | This was not an append that ignored existing data. |
| `operationMetrics` | Writer-reported row/file/byte counts and timing measurements. Timings from this toy run are not production benchmarks. |
| `engineInfo`, `txnId` | Writer software and operation identifier. `txnId` is not the separate `txn` action used for application transaction tracking. |

Null user, notebook or job fields in `DESCRIBE HISTORY` mean those provenance values were not populated, not that the transaction failed.

### `add`, `remove` and statistics

An `add` identifies an active file by `path`, with `partitionValues`, byte `size`, `modificationTime`, `dataChange` and optional statistics. The actual latest add includes `stats`, a JSON-encoded string with `numRecords: 1`, `minValues`, `maxValues` and `nullCount` for the eight business fields. Parse the string as JSON to inspect it. Compatible engines can use these values to skip irrelevant files. [1]

A `remove` is a tombstone for a formerly active path. Here it includes `deletionTimestamp`, `dataChange: true`, `extendedFileMetadata: true`, an empty partition map and the removed file's size. It does not establish that the object was physically deleted.

`dataChange: true` marks a change to table data. An empty partition map is expected for this unpartitioned table. Do not confuse the file's `modificationTime` with an order's event timestamp.

## Schema and protocol inherited from version 0

| Action field | Saved value or meaning |
| --- | --- |
| `metaData.id` | Table identity, not a commit ID. |
| `metaData.format.provider` | `parquet`; `options` is empty. |
| `metaData.schemaString` | JSON-encoded schema with three string columns and five timestamp columns, all nullable. |
| `metaData.partitionColumns` | Empty list: unpartitioned. |
| `metaData.configuration` | Includes `delta.checkpointInterval: 5`. |
| `metaData.createdTime` | Recorded table creation time. |
| `protocol.minReaderVersion` | `1`. |
| `protocol.minWriterVersion` | `2`. |

The eight business columns are `order_id`, `customer_id`, `order_status`, `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date` and `order_estimated_delivery_date`. `order_id` is not a declared primary key. Protocol numbers are compatibility requirements, not Delta Lake package versions.

## What the `.crc` file means

Despite its extension, the latest `.crc` is a JSON version-checksum file, not a data-file checksum or a Parquet checkpoint. Its captured fields are:

| Field | Saved value or role |
| --- | --- |
| `txnId` | Identifies the corresponding transaction. |
| `tableSizeBytes`, `numFiles` | `12443`, `4`, describing active files rather than all retained objects. |
| `numMetadata`, `numProtocol` | Both `1`. |
| `metadata`, `protocol` | Effective table metadata and protocol objects. |
| `allFiles` | Four active file entries in this captured checksum. |
| `setTransactions`, `domainMetadata` | Empty lists. |

The checksum supports validation of reconstructed state. Do not treat an arbitrary `.crc` as a substitute for resolving the committed transaction log. No independent integrity validation of every storage object was run for these guides. [1]

## History, checkpoints and optional files

The inspector saves `DESCRIBE HISTORY` with versions 0, 1 and 2, plus per-commit action counts. Across the three commits it counted five `add`, one `remove`, three `commitInfo`, one `metaData` and one `protocol` action. Five cumulative adds do not mean five currently active files.

Checkpoint files materialize log state, while `_last_checkpoint` helps locate a checkpoint. Neither is present here; the captured history stops at version 2 despite a configured checkpoint interval of 5. No checkpoint result should be invented from that setting. [1]

Other optional file types include deletion vectors, `_change_data` files and checkpoint sidecars. They belong to other enabled features or histories, not this captured run.

For live inspection after a run, use `lab.spark.sql(f"DESCRIBE HISTORY delta.`{root}`").show(truncate=False)` with the notebook's Delta root. The inspector's `history`, `versions`, `total_action_counts` and `checkpoint_files` are saved inspection results, not four additional on-disk system files.

## Limits and sources

Use a Delta reader, not `spark.read.parquet(root)`, to respect log removals. The saved snapshot reports matching business values and no physical removals, but does not prove current object availability, streaming correctness or cross-engine support.

1. [Delta Lake 3.3.2 transaction protocol](https://github.com/delta-io/delta/blob/v3.3.2/PROTOCOL.md), particularly actions, checksums, checkpoints and statistics
2. [Lab metadata inspector](../local-lab/scripts/format_adapters.py) and [Olist configuration](../local-lab/scripts/olist_adapters.py)
