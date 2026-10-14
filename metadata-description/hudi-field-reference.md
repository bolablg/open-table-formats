# Hudi: complete captured-field reference

[Walkthrough](hudi.md) · [Index and evidence scope](README.md) · [Lab capture fields](capture-field-reference.md)

Scope: Hudi 1.2.0, table version 9, timeline layout 2, Copy-on-Write business table. Completed main-table commits and schema records were decoded; auxiliary metadata-table records were not. Definitions do not turn missing payloads into observed facts. Do not edit `.hoodie` files by hand.

## Priority 1: table identity, keys, schema and committed state

### Persistent `hoodie.properties`

Values below came from the create capture. The delete inventory records unchanged size/time for the same object, but does not provide a fresh read of its bytes.

| Property | Purpose and observed interpretation |
| --- | --- |
| `hoodie.table.name` | `olist_orders`: table name used by Hudi and catalog integration. Not a record key. |
| `hoodie.table.type` | `COPY_ON_WRITE`: committed business data is read from base-file slices; row changes rewrite affected base files in this run. |
| `hoodie.table.version` | `9`: storage/table compatibility version. Not package version 1.2.0 or commit count. |
| `hoodie.table.initial.version` | `9`: table version at creation, useful when reasoning about upgrades. |
| `hoodie.table.format` | `native`: Hudi's native table-format implementation, separate from the base-file encoding. |
| `hoodie.table.base.file.format` | `PARQUET`: business base-file encoding. |
| `hoodie.timeline.layout.version` | `2`: timeline storage/naming layout. Not the business table version. |
| `hoodie.timeline.path` | `timeline`: active timeline subpath under `.hoodie`. |
| `hoodie.table.recordkey.fields` | `order_id`: source field used to construct Hudi record keys. A record key is not the same thing as an Iceberg field ID. |
| `hoodie.table.keygenerator.type` | `NON_PARTITION`: nonpartitioned key-generation strategy. |
| `hoodie.table.partition.fields` | Empty: no business partition columns. |
| `hoodie.record.merge.mode` | `COMMIT_TIME_ORDERING`: later transaction ordering governs conflicting records, not the original order purchase timestamp. |
| `hoodie.populate.meta.fields` | `true`: store the five Hudi record metadata fields described below. |

### Completed and inflight commit records

The same record schema appears in completed and some inflight files. An inflight record is preparation/progress information, not proof that its write statistics became committed. Use the completed timeline state.

| Property | Purpose and observed interpretation |
| --- | --- |
| `operationType` | `BULK_INSERT`, `INSERT`, then `DELETE` across completed commits. |
| `partitionToWriteStats` | Map from partition path to file-level write-stat arrays. The only path key is the empty string for the unpartitioned table. |
| `extraMetadata` | Additional string-valued commit metadata. Completed commits contain `schema` and `latest_schema`; the latest inflight record has an empty map. |
| `schema` inside `extraMetadata` | JSON-encoded Avro schema used for the data records, including Hudi metadata columns. |
| `latest_schema` inside `extraMetadata` | JSON-encoded internal schema with field IDs and optionality. Distinct from the Avro schema representation. |
| `compacted` | `false`: these captured commits are not compaction commits. |
| `version` | Commit-metadata serialization version field, null in these decoded records. Do not substitute table version 9 for it. |

### File-level write-stat identity

Names below are relative to one item in `partitionToWriteStats[partition_path]`.

| Property | Purpose and latest DELETE interpretation |
| --- | --- |
| `fileId` | Affected file-group ID, ending `267c8ebfd149-0`. Groups successive versions of the same logical file group. |
| `path` | Replacement file path relative to the table root, ending `_0-159-515_20261006093039842.parquet`. |
| `prevCommit` | Previous file-group commit: `20261006093002958`. The literal string `null` can appear for a new file group; it is not a real commit instant. |
| `prevBaseFile` | Name of the superseded base file, ending `_1-41-138_20261006093002958.parquet`. |
| `partitionPath` | Empty string for this completed unpartitioned write. Can be null in preparatory records. |

### Internal schema and schema-history JSON

| Property | Purpose and interpretation |
| --- | --- |
| `schemas` | Array of internal schema definitions in a `.schemacommit` file. |
| `max_column_id` | Highest internal column ID: `12`. There are 13 fields because IDs start at zero. |
| `version_id` | Internal schema's version marker: `20261006093002958`. Unchanged across this run; a new schema-history filename does not prove a new business schema. |
| `type` at the internal schema root | `record`, describing a row of fields. |
| `fields` | Five Hudi metadata fields plus eight business fields. |
| `id` in an internal field | Stable internal column identity, `0`–`12`. |
| `name` in an internal field | Column name. |
| `optional` | Whether a value may be absent/null. Metadata fields and three lifecycle timestamps are optional; the other business fields are required in this captured Hudi schema. |
| `type` in an internal field | `string` or `timestamp` in this run. |
| `doc` | Field documentation annotation, empty for captured metadata columns. Not data content. |

### Decoded Avro `extraMetadata.schema`

| Property | Purpose and interpretation |
| --- | --- |
| `type` at the Avro root | `record`. Within a timestamp type object it is `long`; within fields it can also be a null/type union. |
| `name` at the Avro root | `olist_orders_record`: Avro record-type name, not a business column. |
| `namespace` | `hoodie.olist_orders`: qualifies the Avro type name. Not a Hive database requirement. |
| `fields` | Ordered Avro field descriptions. |
| `name` in an Avro field | Business or Hudi metadata column name. |
| `type` in an Avro field | A string type, logical type object, or union such as `["null", {...}]`. A union including null represents nullable data. |
| `logicalType` | `timestamp-micros` for timestamps: the physical long represents microseconds since Unix epoch. Distinct from millisecond timeline/provenance values. |
| `default` | `null` for optional fields in the captured schema; an Avro schema default, not evidence that all records contain null. |
| `doc` | Empty text documentation annotation on metadata fields. |

### Hudi record metadata column meanings

| Column | Purpose and interpretation |
| --- | --- |
| `_hoodie_commit_time` | Timeline instant associated with the record's stored version. Not the driver's event time or an order timestamp. |
| `_hoodie_commit_seqno` | Record sequence information within a transaction. Not an order number. |
| `_hoodie_record_key` | Materialized Hudi key derived from the configured record-key fields. |
| `_hoodie_partition_path` | Materialized partition path; empty for this unpartitioned table. |
| `_hoodie_file_name` | Associated data-file name. It changes when a record is rewritten into a new file version. |

These names occur as schema values, not JSON property keys. They are documented because they are central to interpreting Hudi rows; their source-derived record values are not published here.

## Priority 2: change counters, layout and query-planning indexes

### File-level write counters

| Property | Purpose and latest DELETE interpretation |
| --- | --- |
| `numWrites` | Records written into the resulting file: `1`. Can include rewritten survivors; the insert produced `3` writes while inserting `2` new orders. |
| `numInserts` | Insert-record counter, with writer small-file handling potentially converting insert processing into updates. Latest `0`; insert-stage completed stat `2`. |
| `numDeletes` | Records logically deleted in this stat: `1`. |
| `numUpdates` | Update counter inherited from read/merge statistics: `0`. Distinct from the writer's changed-record counter below; population depends on the write path. |
| `numUpdateWrites` | Writer count for records changed through update handling: `0`. Do not use it as a universal synonym for `numWrites` or `numDeletes`. |
| `totalWriteBytes` | Bytes written for this stat: `437175`. |
| `fileSizeInBytes` | Closed output file size: `437175`. A file's stored size and total bytes written need not always match in every write mode. |

### Planning/layout table properties

| Property | Purpose and observed interpretation |
| --- | --- |
| `hoodie.table.metadata.partitions` | `column_stats,files`: metadata indexes marked available/synchronized for readers. These are auxiliary-table partitions, not business partition columns. |
| `hoodie.table.metadata.partitions.inflight` | Empty: no metadata-index partitions listed as still being built in the captured configuration. |
| `hoodie.table.index.defs.path` | `.hoodie/.index_defs/index.json`: relative location of persisted index definitions. |
| `hoodie.table.partition_extractor_class` | Nonpartitioned extractor used for partition/catalog integration. Its `org.apache.hudi.hive` package does not prove a Hive server is required or running. |
| `hoodie.datasource.write.hive_style_partitioning` | `true`: use `column=value` directory conventions when applicable. No business partition fields exist here, so this does not partition the table. |
| `hoodie.datasource.write.drop.partition.columns` | `false`: do not drop partition columns from stored records. No configured partition columns to drop here. |
| `hoodie.datasource.write.partitionpath.urlencode` | `false`: do not URL-encode generated partition path components. No nonempty business partition path here. |
| `hoodie.table.multiple.base.file.formats.enable` | `false`: the table is not configured to mix base-file encodings through that option. |

### Index definition JSON

| Property | Purpose and captured interpretation |
| --- | --- |
| `indexDefinitions` | Map of persisted index definitions. |
| `column_stats` | The map key naming the captured statistics index; not a business column. |
| `indexName` | `column_stats`: definition's name. |
| `indexType` | `column_stats`: index category. |
| `indexFunction` | `column_stats`: function/implementation identifier for this definition. Not a user-defined SQL function executed by this guide. |
| `sourceFields` | Columns covered by the definition: eight business columns plus commit time, record key and partition path. |
| `indexOptions` | Empty map: no extra options persisted in this definition. |
| `version` in the index | `V2`: definition/encoding version marker. Not table version 9 or Hudi 1.2.0. |

The `files` index supports file discovery; `column_stats` supports pruning using file statistics. Actual index payloads were not decoded. An index definition and object inventory do not prove a particular query used the index.

## Priority 3: diagnostics, optional fields and inactive log features

### Remaining persistent table properties

| Property | Purpose and observed interpretation |
| --- | --- |
| `hoodie.timeline.history.path` | `history`: configured archived/history timeline path component. No archived payload appears in this run. |
| `hoodie.archivelog.folder` | `history`: archive-folder configuration retained alongside history-path settings. It does not prove archival ran. |
| `hoodie.table.timeline.timezone` | `LOCAL`: writer's local time zone for timeline instant strings. Do not derive a UTC offset from digits alone. |
| `hoodie.table.cdc.enabled` | `false`: dedicated CDC before/after data capture is not enabled by this setting. Snapshot/incremental access is a different capability. |
| `hoodie.partition.metafile.use.base.format` | `false`: partition metadata is written in the properties-file form rather than the business base-file encoding. Contents of the markers were not captured. |
| `hoodie.table.checksum` | `189955218`: checksum derived from database/table identity in this implementation and used by configuration validation. Not a hash of every property or Parquet file. |

### Optional file/CDC/log fields in write statistics

| Property | Purpose and latest DELETE interpretation |
| --- | --- |
| `tempPath` | Relative temporary-output path when applicable; null. Not proof that no temporary file ever existed during execution. |
| `cdcStats` | Map of CDC file paths to byte sizes when generated; null. No nested CDC payload was captured. |
| `baseFile` | Base file associated with delta/log write statistics; null in this Copy-on-Write stat. Distinct from populated `prevBaseFile`. |
| `logFiles` | Related delta-log file names for log-write statistics; null. |
| `logVersion` | Version of a delta-log file when applicable; null. Not the table version. |
| `logOffset` | Byte position within a delta log when applicable; null. Not a record key or event offset. |
| `minEventTime` | Earliest incoming event time collected for latency accounting, in epoch milliseconds; null. Not a guarantee that Parquet lacks timestamp statistics. |
| `maxEventTime` | Latest incoming event time collected for freshness accounting, in epoch milliseconds; null. Not the commit instant. |

### Log/read/compaction counters in the commit schema

These fields also appear in preparatory records and are inactive in this business-table Copy-on-Write example. Their presence alone does not prove compaction or Merge-on-Read was used.

| Property | Purpose and latest DELETE interpretation |
| --- | --- |
| `totalLogRecords` | Log records processed/compacted in the read/merge path: `0`. Not the business table row count. |
| `totalLogFiles` | Optional log-file count slot in the serialized write-stat schema: null, not a reported zero. |
| `totalLogFilesCompacted` | Log files compacted for the file slice: `0`. |
| `totalLogSizeCompacted` | Total bytes of log files accounted for by compaction: `0`. |
| `totalUpdatedRecordsCompacted` | Records updated through compaction processing: `0`. Not SQL UPDATE count for the whole table. |
| `totalLogBlocks` | Valid log blocks encountered in compaction/read statistics: `0`. |
| `totalCorruptLogBlock` | Corrupt log blocks encountered by that processing path: `0`. This is not a full audit of every stored object. |
| `totalRollbackBlocks` | Rollback blocks encountered in logs: `0`. Does not prove a historical table never had a rollback. |
| `totalLogReadTimeMs` | Time spent reading/merging log records in milliseconds: `0`. |

### Runtime and errors

| Property | Purpose and latest DELETE interpretation |
| --- | --- |
| `totalWriteErrors` | Count of records the write path could not write: `0`. Does not establish every possible kind of correctness. |
| `runtimeStats` | Optional structure of writer timing accumulators. Present on completed writes, null in the latest inflight record. |
| `totalCreateTime` | Insert/new-file-path timing accumulator in milliseconds: `0` in the latest completed stat. |
| `totalScanTime` | Log-block scan/read-and-merge timing accumulator in milliseconds: `0` here. Not total SQL query scan time. |
| `totalUpsertTime` | Existing-file merge-path timing accumulator in milliseconds: `191` here, despite the outer operation being DELETE. Method names identify writer paths, not business operation labels. |

These runtime accumulators are writer diagnostics, not complete end-to-end wall-clock latency. Do not compare them directly with Delta's SQL operation timings or interpret zero as proof that no reading occurred.

## Files whose payloads remain unavailable

| File family | Known role and remaining boundary |
| --- | --- |
| Main `.hoodie_partition_metadata` | Partition/root-depth bookkeeping; presence captured, its actual property values unavailable. |
| Auxiliary `metadata/.hoodie/hoodie.properties` | Configuration for the metadata table, not the business-table properties above. No actual properties decoded. |
| Auxiliary `.deltacommit`, requested and inflight files | Metadata-table timeline actions. Filenames captured; their record fields/values unavailable. |
| Auxiliary `files` HFile and log objects | File-listing index storage. No records decoded. |
| Auxiliary `column_stats` log objects | Statistics index storage. No records decoded; do not invent minima, maxima or null counts. |
| Auxiliary partition markers | Partition bookkeeping for the metadata table's partitions. Payload unavailable. |

The main requested markers and schema requested/inflight markers captured as empty files have no content properties to enumerate. Their names indicate action/state; the completed timeline determines commitment. Avro container headers were not exported either.

## Sources

1. [Hudi 1.2.0 configurations](https://hudi.apache.org/docs/1.2.0/configurations/)
2. [Hudi 1.2.0 timeline](https://hudi.apache.org/docs/1.2.0/timeline/) and [metadata indexes](https://hudi.apache.org/docs/1.2.0/metadata/)
3. [Hudi 1.2.0 commit Avro schema](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/avro/HoodieCommitMetadata.avsc)
4. [Hudi 1.2.0 write statistics](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/java/org/apache/hudi/common/model/HoodieWriteStat.java), [read counters](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/java/org/apache/hudi/common/table/read/HoodieReadStats.java) and [delta-write fields](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/java/org/apache/hudi/common/model/HoodieDeltaWriteStat.java)
5. [Hudi 1.2.0 table configuration implementation](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/java/org/apache/hudi/common/table/HoodieTableConfig.java), including checksum generation
6. [Hudi 1.2.0 partition marker implementation](https://github.com/apache/hudi/blob/release-1.2.0/hudi-common/src/main/java/org/apache/hudi/common/model/HoodiePartitionMetadata.java)
7. [Hudi 1.2.0 timer implementation](https://github.com/apache/hudi/blob/release-1.2.0/hudi-io/src/main/java/org/apache/hudi/common/util/HoodieTimer.java), for elapsed-time units

Interpretations use saved records plus version-pinned schema/source where possible. No auxiliary-file decoding, new experiment, production benchmark or concurrency test was performed for this documentation.
