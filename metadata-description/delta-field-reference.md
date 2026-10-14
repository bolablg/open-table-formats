# Delta Lake: complete captured-field reference

[Walkthrough](delta-lake.md) · [Index and evidence scope](README.md) · [Lab capture fields](capture-field-reference.md)

Scope: Delta Lake 3.3.2, saved table versions 0–2, with the latest state at version 2. A commit file contains separate action objects, one per line. A field is defined in its containing object below; the same spelling in another object can have a different role. Null means not populated, not zero. Do not edit transaction-log files by hand.

## Priority 1: schema, protocol and active files

### Action containers in commit JSON

| Property | Purpose and interpretation |
| --- | --- |
| `metaData` | Replaces the effective table metadata when present. Written in version 0 and inherited by versions 1–2 here. The capitalization is part of the action name. |
| `protocol` | Declares reader/writer compatibility requirements. Recorded in version 0 here. |
| `add` | Adds a logical file to active state, with its partition values and statistics. Version 2 has one. |
| `remove` | Removes a logical file from active state and records a tombstone. Version 2 has one; it does not physically erase the object immediately. |
| `commitInfo` | Operation provenance and metrics. Useful for audit/debugging, but not a replacement for reconciling file actions. |

### `metaData` fields, also present as `metadata` in checksum JSON

| Property | Purpose and interpretation |
| --- | --- |
| `id` | Stable table UUID. Not the version number or a business record key. |
| `format` | Data-file format description, not the table format. |
| `provider` inside `format` | `parquet`. |
| `options` inside `format` | Format-specific options; empty in this capture. |
| `schemaString` | JSON-encoded table row schema. Decode the string before inspecting its fields. |
| `partitionColumns` | Names of table partition columns; empty, so this table is unpartitioned. |
| `configuration` | Persisted table properties; contains the checkpoint setting below. |
| `delta.checkpointInterval` | `5`: writer checkpoint cadence setting. It does not prove that a checkpoint exists; none is captured by version 2. |
| `createdTime` | Table creation time in epoch milliseconds: `1791278982855`. Not an order's purchase timestamp. |

### Decoded `schemaString`

| Property | Purpose and interpretation |
| --- | --- |
| `type` at the schema root | `struct`, identifying a row containing named fields. |
| `fields` | Eight business-column definitions. No extra Hudi-style record metadata fields are present. |
| `name` in a field | Column name. `order_id` is not a declared primary key. |
| `type` in a field | `string` for three columns, `timestamp` for five columns. The lab's UTC convention does not establish the original source time zone. |
| `nullable` | `true` for every business column. Non-null values in a tiny sample do not change this schema rule. |
| `metadata` in a field | Per-column annotations, empty here. Distinct from the checksum's whole-table `metadata` object. |

### `protocol` fields

| Property | Purpose and interpretation |
| --- | --- |
| `minReaderVersion` | `1`: minimum reader protocol needed for this table's features. Not Delta Lake package version 1. |
| `minWriterVersion` | `2`: minimum writer protocol. Later features can require higher versions and explicit feature declarations. |

### `add` and `remove` fields

| Property | Purpose and interpretation |
| --- | --- |
| `path` | Data-file path, relative to the table root in this capture. File membership comes from reconciled actions, not every object found in storage. |
| `partitionValues` | Map of actual partition values used by readers. Empty for both actions here. |
| `size` | Data-file bytes. Latest add: `3111`; remove: `2873`. |
| `dataChange` | `true` for these actions because the operation changes table data. A maintenance rewrite can have different semantics. |
| `modificationTime` in `add` | File creation/modification timestamp in epoch milliseconds: `1791279033000` for the replacement. Not a business-event timestamp. |
| `stats` in `add` | JSON-encoded statistics string, interpreted in Priority 2. |
| `deletionTimestamp` in `remove` | Time of logical removal, in epoch milliseconds: `1791279033841`. Not proof of physical deletion. |
| `extendedFileMetadata` in `remove` | `true`: additional metadata such as partition values and file size is included with the tombstone. |

## Priority 2: statistics and understanding the changes

### Decoded `add.stats`, also embedded in checksum `allFiles`

| Property | Purpose and interpretation |
| --- | --- |
| `numRecords` | Physical records in this file: `1` for the latest add. Not the number of rows in the whole table. |
| `minValues` | Per-column minimum/bound information used by readers for pruning. The map's keys are schema column names. |
| `maxValues` | Per-column maximum/bound information. Statistics describe the file, not a separately maintained latest-driver state. |
| `nullCount` | Per-column null counts, zero for all eight columns in the replacement file. Does not make the columns non-nullable. |

Bounds depend on the format's supported types and writer collection/truncation settings. They are pruning metadata, not a unique-key index. No deletion vectors are active here, so `numRecords` does not need adjustment for them in this run. Source-derived bound values are not republished in these guides.

### `commitInfo` operation fields

| Property | Purpose and interpretation |
| --- | --- |
| `operation` | `WRITE` for versions 0–1 and `DELETE` for version 2. |
| `operationParameters` | Operation-specific details. Values can themselves be serialized JSON strings. |
| `mode` within parameters | `Overwrite` for the initial write, `Append` for the insert. Absent for the DELETE. |
| `partitionBy` within parameters | String `[]`: no partition columns were specified for those writes. |
| `predicate` within parameters | Serialized DELETE condition with Spark expression identifiers. Useful for inspection, not a stable API or a reusable SQL string. |
| `readVersion` | Version read by the transaction: `1` for DELETE, `0` for insert; absent/null for creation. |
| `isolationLevel` | `Serializable` reported for these commits. It is not evidence of a concurrency test in this sequential lab. |
| `isBlindAppend` | Insert is `true`, DELETE is `false`. Describes whether the operation appends without reading/modifying existing data. |
| `operationMetrics` | Map of writer-reported counters. Different operations populate different keys. |

### Write metrics, from versions 0–1

| Property within `operationMetrics` | Purpose and observed values |
| --- | --- |
| `numFiles` | Data files produced: `2` for the initial write and `2` for the insert. Not the resulting table's total file count. |
| `numOutputRows` | Rows produced by the write: `3`, then `2`. |
| `numOutputBytes` | Bytes produced: `5984`, then `6221`. Their sum is `12205` before DELETE. |

### DELETE metrics, from version 2

| Property within `operationMetrics` | Purpose and observed value |
| --- | --- |
| `numRemovedFiles` | Data files removed from active state: `1`. |
| `numRemovedBytes` | Bytes associated with those files: `2873`. |
| `numAddedFiles` | New data files added: `1`. |
| `numAddedBytes` | Bytes in added data files: `3111`. |
| `numDeletedRows` | Business rows logically deleted: `1`. |
| `numCopiedRows` | Surviving rows copied while rewriting affected files: `1`. Not a new business insertion. |
| `numAddedChangeFiles` | Separate change-data files produced: `0`. |
| `numDeletionVectorsAdded` | New deletion-vector descriptors recorded by the operation: `0`. |
| `numDeletionVectorsRemoved` | Earlier deletion-vector descriptors removed: `0`. |
| `numDeletionVectorsUpdated` | Deletion-vector descriptors updated: `0`. These counters do not imply deletion vectors were enabled. |
| `executionTimeMs` | Whole-operation execution metric: `2095` milliseconds. Not dashboard end-to-end latency. |
| `scanTimeMs` | Metric for finding files/rows affected by the DELETE: `1664` milliseconds. Not time spent scanning all historical files by definition. |
| `rewriteTimeMs` | Metric for rewriting affected files: `428` milliseconds. |

The timing components need not sum exactly to the total because of other work and measurement boundaries. These are diagnostics from one tiny local execution, not comparisons between formats.

## Priority 3: integrity, provenance and optional state

### Version checksum (`.crc`) fields

Each checksum contains one JSON object. The latest checksum summarizes version 2, but it is not a data-file CRC or a Parquet checkpoint.

| Property | Purpose and interpretation |
| --- | --- |
| `txnId` | Operation identifier associated with this checksum and commit. Not an application `txn` action's version counter. |
| `tableSizeBytes` | Sum of active data-file sizes: `12443`. Not every retained storage object's bytes. |
| `numFiles` | Active file count: `4`. Distinct from the write metric with the same name. |
| `numMetadata` | Count of effective table-metadata actions in reconstructed state: `1`, not metadata files on storage. |
| `numProtocol` | Count of effective protocol actions in reconstructed state: `1`. |
| `metadata` | Effective table metadata, equivalent to the current `metaData` action's contents. See Priority 1. |
| `protocol` | Effective reader/writer protocol. See Priority 1. |
| `allFiles` | Active `add` file descriptions included in this checksum: four. Uses the same file/statistics fields defined above. Not all retained objects. |
| `setTransactions` | Application transaction records used for idempotent transaction tracking when populated. Empty here. Distinct from UUID-like `txnId`. |
| `domainMetadata` | Feature/domain-specific state when supported and populated. Empty here; domain-metadata actions require writer protocol/feature support not enabled by this table's writer version 2. |

Checksum contents can help validate reconstructed state. No independent object-by-object integrity check was performed for these guides. The transaction log remains the committed-state reference.

### Commit provenance and SQL history fields

| Property | Purpose and interpretation |
| --- | --- |
| `timestamp` | Raw commit epoch milliseconds; latest `1791279033859`. The saved SQL history renders timestamps as ISO strings and may show less precision. |
| `engineInfo` | `Apache-Spark/3.5.7 Delta-Lake/3.3.2`, identifying the writer software. |
| `txnId` | Unique operation identifier recorded in raw commit provenance. Not the table UUID or a record identifier. |
| `version` | In `DESCRIBE HISTORY`, committed table version `0`, `1` or `2`. Not a package version. |
| `userId` | Optional executing-user ID; null here. |
| `userName` | Optional executing-user name; null here. |
| `job` | Optional job provenance structure; null, so no nested job payload was captured. |
| `notebook` | Optional notebook provenance structure; null. Running a notebook does not guarantee this platform-specific value is populated. |
| `clusterId` | Optional cluster identifier; null in this local run. |
| `userMetadata` | Optional custom commit annotation; null. |

SQL history also repeats the operation, parameters, metrics, read version, isolation and blind-append fields defined above. Null provenance does not invalidate a commit.

### Not present in this run

No checkpoint, `_last_checkpoint`, checkpoint sidecar, change-data file or deletion-vector payload was captured. Their file roles are introduced in the walkthrough, but an exhaustive explanation of nonexistent payload fields would be a separate format-specification guide. Empty optional checksum lists are covered above without inventing entries.

## Sources

1. [Delta Lake 3.3.2 protocol](https://github.com/delta-io/delta/blob/v3.3.2/PROTOCOL.md), for actions, schema/statistics serialization, checksums and feature requirements
2. [Delta Lake 3.3.2 DELETE implementation and metric definitions](https://github.com/delta-io/delta/blob/v3.3.2/spark/src/main/scala/org/apache/spark/sql/delta/commands/DeleteCommand.scala)
3. [Lab inspector](../local-lab/scripts/format_adapters.py), for the captured SQL history and action-count envelopes

Definitions were cross-checked against primary documentation/source and the saved captures. The experiment was not rerun. Captured paths and statistics do not prove present object availability or production query performance.
