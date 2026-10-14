# Shared lab capture fields

[Back to the guide index](README.md)

The explorer wraps format metadata in its own JSON. These fields describe **what the inspector saved**, not additional properties in the Iceberg, Delta or Hudi protocol. Source: the lab's [format inspectors](../local-lab/scripts/format_adapters.py), [Olist adapters](../local-lab/scripts/olist_adapters.py) and [evidence server](../local-lab/scripts/explore_evidence.py).

## Priority 1: identify the evidence and distinguish physical from logical state

| Field | Meaning |
| --- | --- |
| `format` | Which format the captured section describes. |
| `root` | Table's storage URI. A root does not identify a committed version on its own. |
| `metadata` | Inspector-produced format-specific metadata summary. Not the same as a format's identically named internal field. |
| `raw_metadata` | Captured text or decoded records from selected generated metadata objects, with limits below. |
| `inventory` | Saved physical-object listing; includes retained files that may no longer be logically active. |
| `path` in inventory/raw-file entries | Object URI. |
| `size_bytes` | Physical object's size, not total active table bytes. |
| `modified_ms` | Storage modification time in milliseconds, not the latest business event or a commit authority. |
| `file_changes` | Comparison with the preceding saved physical inventory. |
| `added` | Objects newly present in that comparison. Not automatically newly inserted business rows. |
| `removed` | Objects no longer present. Empty after the reference DELETE despite logical file removal. |
| `changed` | Objects whose observed size/time changed at the same path. |
| `before` | Previous inventory entry for a changed object. |
| `after` | New inventory entry for that object. |
| `change_basis` | Explains that physical differences use presence, size and modification time. Not a byte-for-byte content hash. |
| `reader_command` | Format-aware inspection command saved for the explorer; requires the corresponding table objects/runtime to exist. |
| `reader_language` | Display language for that command. |

## Priority 2: metadata inspection results

| Field | Meaning |
| --- | --- |
| `metadata_json_files` | Iceberg metadata JSON paths found in storage. More than one can be retained; this list alone does not choose the current snapshot. |
| `system_tables` | Saved Iceberg SQL metadata views: `history`, `snapshots`, `manifests`, `files`. |
| `history` | Iceberg current-snapshot history or Delta SQL commit history, depending on the enclosing format. See its field reference. |
| `snapshots` | Saved Iceberg snapshot records. |
| `manifests` | Saved Iceberg current-manifest view. |
| `files` in `system_tables` | Envelope for the current Iceberg files-view result. Different from `raw_metadata.files`. |
| `row_count` in the files envelope | Total metadata-view rows counted. Counts file entries, not business rows. |
| `sample` | Bounded records saved from that view; not guaranteed to include every file in a larger table. |
| `versions` | Delta per-log-file action-count summaries, not copies of complete snapshots. |
| `log_file` | Delta commit JSON path for one summary. |
| `actions` | Counts by action name in that commit. Action names are defined in the Delta reference. |
| `total_action_counts` | Cumulative action counts across inspected commits. Five adds minus one remove leaves four active files in this run. |
| `checkpoint_files` | Delta checkpoint paths found; empty here. |
| `table_type` | Hudi business-table type reported by this lab's configured adapter: `COPY_ON_WRITE`. |
| `timeline_files` | Main Hudi timeline file paths identified by the inspector. Includes state markers as well as completed actions. |
| `auxiliary_timeline_files` | Separately listed Hudi metadata-table timeline paths. |
| `parquet_file_count` | Physical business-table Parquet objects, excluding auxiliary metadata-table objects: four at delete, not four active file slices. |
| `merge_on_read_log_file_count` | Physical business-table log objects, excluding auxiliary objects: zero. |
| `merge_on_read_note` | Explains the configured Copy-on-Write scope and separate auxiliary logs. |
| `auxiliary_metadata_table` | Separate summary of Hudi metadata-table physical objects. |
| `log_objects` | Auxiliary log count: twelve at delete. Not business-table log count. |
| `parquet_objects` | Auxiliary Parquet count: zero. Does not mean no auxiliary base files; an HFile is present. |

## Priority 3: decoding boundaries and diagnostic text

| Field | Meaning |
| --- | --- |
| `candidate_count` | Number of eligible raw metadata objects discovered by the capture selector. Not all storage objects. |
| `inline_limit` | Maximum number of eligible objects captured inline: twelve. |
| `files` inside `raw_metadata` | Selected objects whose text/records are included. This list is not the current active data-file set. |
| `encoding` | How the inspector decoded the object, such as UTF-8 text or Avro records. Not the table format. |
| `text` | Saved text contents, potentially containing JSON, JSON Lines, properties or an empty marker. Embedded structured strings need a second decoding step. |
| `records` | Decoded Avro records, not original binary Avro bytes or a dump of its container header. |
| `truncated` | Whether the decoded record view was cut short by capture limits. False for the displayed Avro records in this run; absence of this flag on a text entry is not a universal no-truncation contract. |
| `note` | Capture/auxiliary-scope explanation. Read it before interpreting counts or declaring coverage. |
| `what_to_notice` | Human-readable inspector guidance, not an engine property. |
| `error` | Diagnostic text saved when an inspection fails, if present in another run. An error result is not an empty but successfully inspected table. |

The saved reference metadata has no decoded auxiliary Hudi payloads. A filename in an inventory establishes only observed presence at capture time, not its contents, current availability or correct behavior.
