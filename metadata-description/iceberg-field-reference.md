# Iceberg: complete captured-field reference

[Walkthrough](iceberg.md) · [Index and evidence scope](README.md) · [Lab capture fields](capture-field-reference.md)

Scope: the saved 3 → 5 → 4 run, Iceberg 1.11.0, table format v2. Names below are relative to the stated object. Each map/array has one structural definition; column names and IDs inside it are lookup keys. A null optional value means not supplied or not applicable, not automatically zero or corruption. Do not edit metadata files by hand.

## Priority 1: identify the table and its committed state

### Table metadata JSON

| Property | Purpose and interpretation |
| --- | --- |
| `format-version` | Storage specification version: `2`. Not the library version or number of snapshots. |
| `table-uuid` | Stable table identity. Distinguishes this table from a different table at a reused location. |
| `location` | Base URI for table storage, ending `/iceberg/lab/orders`; not a declaration that every object below it is active. |
| `current-snapshot-id` | Default current data state: `5484902428416146878`. |
| `refs` | Named snapshot references. Only the `main` branch is captured. |
| `main` | The default branch entry inside `refs`, not a second table. |
| `snapshot-id` inside `refs.main` | Snapshot selected by that reference; equals `current-snapshot-id`. |
| `type` inside `refs.main` | Reference kind: `branch`. A branch can advance; a tag is a different reference kind. |
| `snapshots` | Available snapshot descriptions retained in this JSON; three in the saved state. Availability still depends on referenced files. |
| `current-schema-id` | Selects schema `0` from `schemas`. |
| `schemas` | List of schema definitions; one definition here. Not one schema per Parquet file. |
| `last-sequence-number` | Largest snapshot sequence assigned so far: `3`. |
| `default-spec-id` | Default partition specification for new writes: `0`. |
| `partition-specs` | Known partition specifications, including older ones if evolved. One unpartitioned spec here. |
| `default-sort-order-id` | Default declared writer sort order: `0`, meaning unsorted. |
| `sort-orders` | Known sort definitions. Here order 0 has no sort fields. |

### Schema, partition-spec and sort-order objects

| Property | Purpose and interpretation |
| --- | --- |
| `type` in a schema | `struct`: the table row is a collection of named fields. |
| `schema-id` | Identifies a schema version; `0` here. Snapshot schema IDs refer to these definitions. |
| `fields` in a schema | Eight business-column definitions. The names/types/nullability are listed in the walkthrough. |
| `id` in a schema field | Stable column identity, `1` through `8`. A rename is not supposed to create a new identity for the same column. |
| `name` in a schema field | Human-readable column name, such as `order_id`; not a primary-key declaration. |
| `required` | `false` for all eight columns, allowing nulls. |
| `type` in a schema field | `string` for the three text fields; `timestamptz` for the five timestamp instants. Named source time zones are not preserved by this type. |
| `spec-id` | Partition-spec identity: `0`. |
| `fields` in a partition spec | Empty, so the table is unpartitioned. No partition-transform fields were captured to interpret. |
| `order-id` | Sort-order identity: `0`. |
| `fields` in a sort order | Empty, so no declared sort transforms or directions apply. |

### Snapshot objects

| Property | Purpose and interpretation |
| --- | --- |
| `sequence-number` | Commit ordering for snapshots; `1`, `2`, `3` in this run. |
| `snapshot-id` | Opaque snapshot identity. Do not use numeric order as chronology or round it through JavaScript floating-point numbers. |
| `parent-snapshot-id` | Previous data state on this lineage; absent for the first snapshot, then linked to the preceding snapshot. |
| `timestamp-ms` | Snapshot creation time as milliseconds since Unix epoch; latest `1791279029768`. |
| `schema-id` | Schema associated with the snapshot: `0` throughout. |
| `manifest-list` | URI of the Avro list describing that snapshot's manifests. |
| `summary` | Operation and writer-reported metrics. Counts describe different things, as detailed below. |

### Manifest entries and data-file identity

| Property | Purpose and interpretation |
| --- | --- |
| `status` | Entry state: `0` existing, `1` added, `2` deleted. Deleted entries are not active data files. |
| `snapshot_id` | Snapshot associated with an entry's addition/removal. Uses underscores in Avro, unlike JSON snapshot fields. |
| `sequence_number` in an entry | Data sequence number, used to order data relative to deletes. Null added-entry values can inherit from the manifest. |
| `file_sequence_number` | Sequence when the physical file was added. Distinct from data sequence when an operation preserves older data ordering. Null can use inheritance. |
| `data_file` | Nested description of the file represented by this entry. |
| `content` in `data_file` | `0` for data, `1` for position deletes, `2` for equality deletes. All captured business entries are data files. |
| `file_path` | Object URI read by the engine. Its presence in an active entry, not a directory listing alone, determines membership. |
| `file_format` | `PARQUET`. Separate from the table format. |
| `partition` | Typed partition-value tuple. Empty here because there are no partition fields. |
| `record_count` | Physical records in the file. The replacement has `1`; the removed file had `2`. |
| `file_size_in_bytes` | Full file size, including format overhead. Replacement: `3104` bytes. |

## Priority 2: planning, statistics and explaining changes

### Manifest-list records

| Property | Purpose and interpretation |
| --- | --- |
| `manifest_path` | URI of the manifest whose entries are to be considered. |
| `manifest_length` | Manifest object's byte length, not the sum of its data-file sizes. |
| `partition_spec_id` | Spec used by this manifest: `0`. Needed to interpret its partition tuples. |
| `content` in a manifest list | `0` data manifest, `1` delete manifest. This enum differs from `data_file.content`; all three current manifests are data manifests. |
| `sequence_number` in a manifest list | Sequence when that manifest was added; current list contains sequences `3`, `2`, `3`. |
| `min_sequence_number` | Smallest data sequence among live entries in the manifest: `3`, `2`, `1` respectively. Helps reason about which deletes can apply. |
| `added_snapshot_id` | Snapshot that introduced this manifest. A reused manifest retains its original attribution. |
| `added_files_count` | Entries marked added within that manifest: `1`, `2`, `0` in current-list order. Not necessarily additions in the latest commit. |
| `existing_files_count` | Entries marked existing: `0`, `0`, `1`. |
| `deleted_files_count` | Entries marked deleted: `0`, `0`, `1`. Does not count physical storage deletions. |
| `added_rows_count` | Records in added entries: `1`, `2`, `0`. |
| `existing_rows_count` | Records in existing entries: `0`, `0`, `1`. |
| `deleted_rows_count` | Records in deleted entries: `0`, `0`, `2`. These do not all represent logically deleted business rows. |
| `partitions` | Per-partition-field summaries used to prune manifests. Empty here. No nested partition-summary fields are present in this capture. |

### Data-file statistics and read layout

| Property | Purpose and interpretation |
| --- | --- |
| `column_sizes` | Map from field ID to column storage size in bytes. Not an average row width or a row count. |
| `value_counts` | Counts of values, including nulls, keyed by field ID. Nested data can make these differ from file record counts. Here every column in the replacement has count `1`. |
| `null_value_counts` | Null counts by field ID; all replacement-file counts are zero, despite nullable schema fields. |
| `nan_value_counts` | NaN counts for floating-point fields. Empty because this schema has no float/double columns. |
| `lower_bounds` | Encoded lower bounds by field ID. Values can be truncated conservatively; not always the exact minimum. |
| `upper_bounds` | Encoded upper bounds by field ID. A shortened string's upper bound may deliberately exceed the actual string. |
| `key` in decoded Avro metric maps | Schema field ID. This is the Avro map-entry representation, not an order's business key. |
| `value` in decoded Avro metric maps | The count, size or encoded bound for that field ID. Its interpretation depends on the containing metric map. |
| `split_offsets` | Recommended byte starting points for read splits, such as row-group starts. `[4]` is not a row number. |
| `sort_order_id` | Declared sort-order identity for this file: `0`, unsorted. |

### Snapshot summary: latest values unless stated otherwise

| Property | Purpose and interpretation |
| --- | --- |
| `operation` | `append` for create/insert; `overwrite` for the copy-on-write DELETE's file replacement. |
| `added-data-files` | New data files in this commit: `1`. |
| `deleted-data-files` | Data files removed from this snapshot's active set: `1`. |
| `added-records` | Records in added data files: `1`, the surviving order rewritten to a replacement. |
| `deleted-records` | Records in removed data files: `2`; only one business order was logically deleted. |
| `added-files-size` | Bytes in files added by the commit: `3104`. |
| `removed-files-size` | Bytes in files removed from active state: `3063`. |
| `changed-partition-count` | Logical groups touched: `1`, the unpartitioned group. |
| `total-data-files` | Live data files after the commit: `4`. |
| `total-records` | Records in live data files before applying separate deletes. Here `4` also equals query-visible rows because there are no delete files. |
| `total-files-size` | Live file bytes: `12288`. Excludes retained objects not in the current snapshot. |
| `total-delete-files` | Live separate delete files: `0`. |
| `total-position-deletes` | Position-delete record count: `0`. |
| `total-equality-deletes` | Equality-delete record count: `0`. |
| `manifests-created` | Manifest files created by this operation: `2`. |
| `manifests-kept` | Earlier manifests reused unchanged: `1`. |
| `manifests-replaced` | Earlier manifests superseded by rewritten manifests: `1`. Not proof of physical removal. |

### Writer properties

| Property within `properties` | Purpose and interpretation |
| --- | --- |
| `write.update.mode` | `copy-on-write`: configured updates rewrite affected files rather than recording separate row-level delete files. No UPDATE was executed in this automated run. |
| `write.delete.mode` | `copy-on-write`: the captured DELETE replaces the affected data file. |
| `write.parquet.compression-codec` | `zstd`: Zstandard for Parquet writes. Does not imply that every future writer must produce identically sized files. |
| `owner` | `spark`: descriptive ownership label, not an IAM enforcement mechanism. |

## Priority 3: history, diagnostics and optional features

### Table bookkeeping and logs

| Property | Purpose and interpretation |
| --- | --- |
| `last-updated-ms` | Most recent metadata update timestamp; not the newest order event time. |
| `last-column-id` | Highest assigned schema field ID: `8`. Helps prevent ID reuse during evolution. |
| `last-partition-id` | Highest partition-field ID bookkeeping value: `999`, the no-fields initialization value here. |
| `snapshot-log` | Records when a snapshot became current. Not necessarily identical to all snapshots in a branched or rolled-back table. |
| `timestamp-ms` in `snapshot-log` | Time of the current-snapshot transition. |
| `snapshot-id` in `snapshot-log` | Snapshot selected by that transition. |
| `metadata-log` | Retained references to previous metadata JSON files; v1 and v2 here. History can be pruned. |
| `timestamp-ms` in `metadata-log` | Recorded metadata-history timestamp for that prior metadata entry. |
| `metadata-file` | URI of the previous metadata JSON, not a Parquet data file. |
| `statistics` | Separate table statistics-file descriptors. Empty; this says nothing about the presence of manifest metrics. |
| `partition-statistics` | Separate partition statistics-file descriptors. Empty. |
| `version-hint.text` | File contents `3`: Hadoop-catalog discovery hint, not a universal catalog commit protocol. |

### Snapshot provenance

| Property within `summary` | Purpose and interpretation |
| --- | --- |
| `spark.app.id` | Spark application's identifier, `local-1791278966905`. A property name containing literal dots, not nested JSON objects. |
| `app-id` | Application identifier recorded by the writer; same identifier here. |
| `app-name` | Writer application label: `open-table-formats-lab-1`. |
| `engine-name` | `spark`. |
| `engine-version` | `3.5.7`. |
| `iceberg-version` | Iceberg 1.11.0 and its build commit, distinct from table format v2. |

### Optional file fields, including columns exposed by newer reader schemas

| Property | Purpose and interpretation |
| --- | --- |
| `key_metadata` | File encryption/key-retrieval metadata, when supplied. Null in both manifest-list and data-file records here. Null alone is not proof that the object store lacks encryption. |
| `equality_ids` | Column IDs used to match equality-delete rows. Null for these ordinary data files. |
| `referenced_data_file` | Target data-file URI for applicable delete metadata. Null in this capture. |
| `first_row_id` | Start of a v3 row-lineage ID range. Exposed as null by this reader's files view; the table remains v2. Not the `order_id` column. |
| `content_offset` | Byte offset of referenced content, used for v3 deletion-vector blobs. Null; no such feature is active here. |
| `content_size_in_bytes` | Referenced blob length, paired with that offset. Null, not a zero-sized business file. |

### SQL metadata view fields

These are engine-produced views of metadata, not extra files. File identity and metrics use the definitions above.

| Property | View and interpretation |
| --- | --- |
| `made_current_at` | `history`: time a snapshot became current. |
| `is_current_ancestor` | `history`: whether that entry belongs to the current snapshot's ancestry; true for all three here. |
| `parent_id` | `history`/`snapshots`: parent snapshot ID; null for the initial snapshot. |
| `snapshot_id` | Snapshot identity in SQL's underscore naming. |
| `committed_at` | `snapshots`: commit timestamp representation. |
| `manifest_list` | `snapshots`: same pointer as JSON `manifest-list`. |
| `operation` | `snapshots`: operation label from the summary. |
| `summary` | `snapshots`: summary map described above. |
| `path` | `manifests`: manifest URI, not a data-file URI. |
| `length` | `manifests`: manifest byte size. |
| `partition_spec_id` | `manifests`: spec identity used by that manifest. |
| `added_snapshot_id` | `manifests`: snapshot that introduced the manifest. |
| `content` | `manifests`: manifest kind, using the list enum `0` data / `1` deletes. |
| `added_data_files_count` | `manifests`: added data-file entries. |
| `existing_data_files_count` | `manifests`: existing data-file entries. |
| `deleted_data_files_count` | `manifests`: deleted data-file entries, not physically deleted objects. |
| `added_delete_files_count` | `manifests`: added delete-file entries; zero here. |
| `existing_delete_files_count` | `manifests`: existing delete-file entries; zero here. |
| `deleted_delete_files_count` | `manifests`: removed delete-file entries; zero here. |
| `partition_summaries` | `manifests`: partition-field summaries; empty here. |
| `spec_id` | `files`: partition-spec identity for that file. |
| `readable_metrics` | `files`: named, decoded per-column metrics rather than binary bound values. |
| `column_size` | Per-column decoded byte size; counterpart of `column_sizes`. |
| `value_count` | Per-column decoded count including nulls. |
| `null_value_count` | Per-column decoded null count. |
| `nan_value_count` | Per-column decoded NaN count, null when not supplied/applicable. |
| `lower_bound` | Decoded lower bound; truncation caveats still apply. |
| `upper_bound` | Decoded upper bound; not necessarily the exact maximum string. |

For the `files` capture envelope's `row_count` and `sample`, see the shared reference. Four rows in this metadata view mean four active file entries, not four business rows by definition; they happen to match in this run.

## Sources and interpretation boundaries

1. [Iceberg specification](https://iceberg.apache.org/spec/), for table metadata, v2 manifests, sequence inheritance and optional v3 fields. Later-version fields are identified explicitly, not attributed to v2.
2. [Iceberg 1.11.0 Spark metadata queries](https://iceberg.apache.org/docs/1.11.0/spark-queries/)
3. [Iceberg 1.11.0 configuration](https://iceberg.apache.org/docs/1.11.0/configuration/)
4. [Iceberg 1.11.0 Hadoop table operations](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/hadoop/HadoopTableOperations.java)

Values were checked against saved captures, not newly queried from storage. Avro container-header metadata was not exported by the inspector; decoded records are covered here, not an invented header dump. No benchmark or concurrency guarantee was tested.
