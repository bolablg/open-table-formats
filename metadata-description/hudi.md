# Apache Hudi: timeline, file groups and metadata table

[Back to the guide index](README.md)

For every captured property, grouped by importance, see the [complete field reference](hudi-field-reference.md).

The reference run ends with **4 business rows** after a DELETE. Hudi **1.2.0** writes a **Copy-on-Write** business table, with table version **9** and timeline layout **2**. Its auxiliary metadata table has its own timeline and log files; those do not make the business table Merge-on-Read.

## Latest metadata and system file map

Paths are relative to `hudi/orders/` in the reference run.

| File or family | Role | Capture status |
| --- | --- | --- |
| `.hoodie/timeline/20261006093039842_20261006093042365.commit` | Latest completed business-table DELETE commit. | Avro record decoded at delete. |
| `.hoodie/timeline/20261006093039842.commit.requested` | Requested-state marker for that operation. | Empty text captured. |
| `.hoodie/timeline/20261006093039842.inflight` | Inflight metadata for that operation. | Avro record decoded at delete. |
| `.hoodie/.schema/20261006093039842_20261006093041338.schemacommit` | Latest schema-history file. | JSON text captured at delete. |
| `.hoodie/.schema/20261006093039842.schemacommit.requested` and `.schemacommit.inflight` | Schema-action state markers. | Empty text captured. |
| `.hoodie/hoodie.properties` | Persistent business-table configuration. | Text captured at create; same path, byte size and modification time in the final inventory. Contents were not reread at delete. |
| `.hoodie/.index_defs/index.json` | Column-statistics index definition. | Text captured at create; same path, byte size and modification time in the final inventory. |
| `.hoodie_partition_metadata` | Partition marker at the unpartitioned business-table root. | Inventory only; payload not captured. |
| `.hoodie/metadata/.hoodie/hoodie.properties` | Auxiliary metadata-table configuration. | Inventory only. Do not substitute the business-table properties. |
| `.hoodie/metadata/.hoodie/timeline/*` | Auxiliary metadata-table requested/inflight/completed delta commits. | Inventory only. Latest completed filename ends `20261006093039842_20261006093042135.deltacommit`. |
| `.hoodie/metadata/files/*` | File-listing index storage, including an HFile base file and log objects. | Inventory only; no payload decoding. |
| `.hoodie/metadata/column_stats/*` | Column-statistics index log objects. | Inventory only; no payload decoding. |
| `.hoodie/metadata/files/.hoodie_partition_metadata`, `.hoodie/metadata/column_stats/.hoodie_partition_metadata` | Auxiliary partition markers. | Inventory only. |

The older create/insert main-table `.commit`, requested, inflight and schema files also remain in the inventory. No clean, rollback, replacecommit, archived-history, temporary-marker or business-table log objects appear in this saved inventory. This is an observation about this short run, not a list of all files Hudi can generate.

The delete raw viewer captured 12 of 20 eligible main-table objects. In addition to the latest six timeline/schema files above, it captured the corresponding six insert-stage files. Auxiliary objects and partition marker payloads were outside that decoded set.

## Follow the completed timeline

| Lab step | Requested instant | Completed main-table file | Business rows afterward |
| --- | --- | --- | ---: |
| Initial write | `20261006093002958` | `20261006093002958_20261006093013934.commit` | 3 |
| Insert | `20261006093024459` | `20261006093024459_20261006093027345.commit` | 5 |
| Delete | `20261006093039842` | `20261006093039842_20261006093042365.commit` | 4 |

Timeline layout 2 completed filenames include the requested and completion instants. The captured properties specify timeline time zone `LOCAL`; do not assign a UTC offset from these filenames alone. Requested/inflight files remaining beside a completed commit are not, by themselves, evidence of a failed operation. Readers resolve timeline state, not just individual suffixes. [1]

```text
Table properties + completed timeline + file-group view
  → latest committed file slice for each file group
    → current business rows

Auxiliary metadata table
  → accelerates file discovery and statistics lookup
```

## Interpret the latest completed DELETE commit

The `.commit` suffix does not mean JSON text: the captured Hudi 1.2.0 commit is an Avro record. Its main fields are:

| Field | Saved value or interpretation |
| --- | --- |
| `operationType` | `DELETE`. |
| `partitionToWriteStats` | One entry under the empty partition path, containing one affected file group's write statistics. |
| `extraMetadata.schema` | JSON-encoded Avro record schema, including Hudi metadata fields. |
| `extraMetadata.latest_schema` | JSON-encoded internal schema with column IDs. |
| `compacted` | `false`; this commit is not a compaction result. |
| `version` | Null in this decoded record. It does not replace the table version 9 in `hoodie.properties`. |

The affected write-stat record reports:

| Field | Saved value or interpretation |
| --- | --- |
| `fileId` | `cd9c3b2b-a522-4d5e-884e-267c8ebfd149-0`, identifying the affected file group. |
| `path` | New base file ending `_0-159-515_20261006093039842.parquet`. |
| `prevBaseFile` | Previous base file ending `_1-41-138_20261006093002958.parquet`. |
| `prevCommit` | `20261006093002958`. |
| `numDeletes` | `1` business record removed. |
| `numWrites` | `1` record written to the replacement file. |
| `numInserts`, `numUpdates`, `numUpdateWrites` | All zero in this DELETE statistic. |
| `fileSizeInBytes`, `totalWriteBytes` | Both `437175` for the replacement. |
| `partitionPath` | Empty: unpartitioned table. |
| `totalWriteErrors` | `0` reported by this writer. |
| `runtimeStats` | Recorded operation timings, not a benchmark. |
| `baseFile`, `logFiles`, `cdcStats`, `tempPath`, `minEventTime`, `maxEventTime` | Null in this record. Do not infer missing event-time bounds from the filename. |
| Other `totalLog*`, rollback, corruption and compaction counters | Zero or null here; no business-table log processing is recorded. |

The old two-row base file was superseded by a one-row file. The other file group had already been rewritten by the insert: that replacement contains three rows. The latest file slices therefore contain **3 + 1 = 4** business rows. The insert's `numWrites: 3` and `numInserts: 2` illustrate the same distinction between rewritten survivors and new business rows.

Four business Parquet objects remain physically stored, but only two latest base-file slices represent the current business table. The inventory's Parquet count is not an active-file count.

## Schema commits and metadata columns

The latest completed schema-history file contains `schemas`, with `max_column_id: 12`, `version_id: 20261006093002958`, record type and 13 fields. The schema version remains the initial instant even though a later schema-history filename was created: the create/insert/delete sequence did not add a business column.

| Field IDs | Fields | Saved internal schema |
| --- | --- | --- |
| 0–4 | `_hoodie_commit_time`, `_hoodie_commit_seqno`, `_hoodie_record_key`, `_hoodie_partition_path`, `_hoodie_file_name` | Optional strings. |
| 5–7 | `order_id`, `customer_id`, `order_status` | Required strings. |
| 8 | `order_purchase_timestamp` | Required timestamp. |
| 9–11 | `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date` | Optional timestamps. |
| 12 | `order_estimated_delivery_date` | Required timestamp. |

The Avro schema uses `timestamp-micros` logical types over longs; nullable timestamp fields use unions with null. This Hudi schema's nullability differs from the all-nullable Iceberg/Delta schemas in the reference run. Matching saved business values does not mean identical physical schemas.

The five `_hoodie_*` fields track record commit, sequence, key, partition and file information. They are not extra Olist business columns. [2]

## Table properties

These settings were decoded from the create-stage business-table `hoodie.properties`. No new payload was captured at delete; the final inventory reports unchanged size and modification time.

| Property or related group | Observed setting and purpose |
| --- | --- |
| `hoodie.table.name` | `olist_orders`. |
| `hoodie.table.type` | `COPY_ON_WRITE`. |
| `hoodie.table.version`, `hoodie.table.initial.version` | Both `9`, distinct from package version 1.2.0. |
| `hoodie.timeline.layout.version` | `2`. |
| `hoodie.timeline.path` | `timeline`. |
| `hoodie.timeline.history.path`, `hoodie.archivelog.folder` | `history`; no archived files are present in the captured inventory. |
| `hoodie.table.timeline.timezone` | `LOCAL`. |
| `hoodie.table.recordkey.fields` | `order_id`, used as the Hudi record key. |
| `hoodie.table.keygenerator.type` | `NON_PARTITION`. |
| `hoodie.table.partition.fields` | Empty. |
| `hoodie.table.partition_extractor_class` | `org.apache.hudi.hive.NonPartitionedExtractor`; the class name does not establish that a Hive service is running. |
| `hoodie.record.merge.mode` | `COMMIT_TIME_ORDERING`, not ordering by the order's business timestamp. |
| `hoodie.table.format`, `hoodie.table.base.file.format` | `native`, `PARQUET`. |
| `hoodie.table.multiple.base.file.formats.enable` | `false`. |
| `hoodie.populate.meta.fields` | `true`, enabling the five Hudi metadata fields. |
| `hoodie.table.metadata.partitions` | `column_stats,files`. |
| `hoodie.table.metadata.partitions.inflight` | Empty. |
| `hoodie.table.index.defs.path` | `.hoodie/.index_defs/index.json`. |
| `hoodie.table.cdc.enabled` | `false`. Do not assume a before/after change-data feed is present. |
| `hoodie.datasource.write.drop.partition.columns` | `false`. |
| `hoodie.datasource.write.hive_style_partitioning` | `true`, but no partition fields are configured here. |
| `hoodie.datasource.write.partitionpath.urlencode` | `false`. |
| `hoodie.partition.metafile.use.base.format` | `false`. |
| `hoodie.table.checksum` | `189955218`, table-identity checksum used during configuration validation. In this implementation it is derived from the database/table name, not every configuration property or data file. |

The [Olist adapter](../local-lab/scripts/olist_adapters.py) configures the nonpartitioned record key and merge mode; the [base adapter](../local-lab/scripts/format_adapters.py) enables metadata and disables automatic cleaning for this exercise. Not every writer option is persisted in `hoodie.properties`. [3]

## Index definition and auxiliary files

The captured `.index_defs/index.json` defines `column_stats` with `indexName`, `indexType`, `indexFunction`, `sourceFields`, empty `indexOptions` and `version: V2`. Its source fields include the eight business columns plus commit time, partition path and record key. `V2` is this index encoding/configuration marker, not the Hudi package version.

The final inventory shows an auxiliary `files` HFile and **12 auxiliary log objects**: four in `files`, eight in `column_stats`. Main-table data-log count is zero. The metadata table stores indexes for file discovery and statistics, with its own timeline. Its payloads were not decoded here, so these guides do not assert their exact contents or benchmark pruning effectiveness. [4]

Partition markers help identify Hudi partitions and their relationship to the table root. Their presence does not mean this business table has a user-defined partition column; their actual property values were not captured. The marker role is documented in the version-pinned implementation. [5]

## Limits and sources

Read with the Hudi reader, for example the explorer's `lab.spark.read.format("hudi").load(root)`, not all Parquet files at the root. The saved validation reports matching business values; the physical inventory does not by itself establish current logical state or current storage availability. No new experiment or binary auxiliary-file decoding was performed for these guides.

1. [Hudi 1.2.0 timeline](https://hudi.apache.org/docs/1.2.0/timeline/)
2. [Hudi technical specification](https://hudi.apache.org/learn/tech-specs/), for file groups, schemas and metadata fields; actual values above come from the saved 1.2.0 run
3. [Hudi 1.2.0 configurations](https://hudi.apache.org/docs/1.2.0/configurations/)
4. [Hudi 1.2.0 metadata table](https://hudi.apache.org/docs/1.2.0/metadata/)
5. [Hudi 1.2.0 partition marker implementation](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/java/org/apache/hudi/common/model/HoodiePartitionMetadata.java)
