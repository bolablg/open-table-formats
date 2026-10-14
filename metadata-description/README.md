# Metadata descriptions

Start here to understand how the lab's three formats turn stored files into a committed table. These guides explain the latest **saved lab state**, not the latest upstream format releases and not a live storage inventory.

## Choose a guide

| Guide | Start with | What it explains |
| --- | --- | --- |
| [Apache Iceberg](iceberg.md) | `metadata/v3.metadata.json` | Schema, snapshots, manifest lists, manifests, file statistics, version hint and SQL metadata tables. |
| [Delta Lake](delta-lake.md) | `_delta_log/00000000000000000002.json` | Commit actions, inherited schema and protocol, file statistics, checksum files, history and checkpoints. |
| [Apache Hudi](hudi.md) | Latest completed `.commit` | Timeline states, file groups, schema commits, table properties, index definitions and the auxiliary metadata table. |

Read the latest-state example first, then the file map and field descriptions. Filenames below are relative to each format's table root unless stated otherwise. The formats do not share one metadata layout or one version counter.

## Complete captured-field references

The walkthroughs above explain the story. For individual properties, use the references below. Each groups fields by importance, gives their purpose and interprets their observed value or absence:

- [Iceberg field reference](iceberg-field-reference.md)
- [Delta Lake field reference](delta-field-reference.md)
- [Hudi field reference](hudi-field-reference.md)
- [Shared lab capture fields](capture-field-reference.md), which belong to the inspector rather than a table-format specification

**Priority 1: table correctness** covers identity, schema, committed state and file membership. **Priority 2: planning and change interpretation** covers statistics, layout and operation counts. **Priority 3: diagnostics and optional features** covers provenance, timings, integrity helpers and inactive fields. Priority is a reading order, not permission for an implementing engine to ignore protocol fields.

Coverage means every property name in the decoded reference-run metadata, including embedded JSON schemas/statistics and SQL metadata views. Repeated map keys such as column IDs, column names and partition paths are data keys, not new property definitions. Older create/insert captures supply properties inherited by the latest state. Uncaptured payloads remain explicitly unavailable; this is not a dictionary of every possible field in every format release.

## Evidence and versions

The reference run is `olist_article_3_2_1_20261006T092918Z_a1e10448`. Its final automated snapshot was captured at **2026-10-06T09:30:43.403101Z**, after create, insert and delete: **3 → 5 → 4 business rows**. Saved validations report four unique keys and matching business values for each format.

| Component | Version or setting in this run |
| --- | --- |
| Spark | 3.5.7 |
| Iceberg | 1.11.0; table format v2; copy-on-write updates and deletes |
| Delta Lake | 3.3.2; minimum reader protocol 1, writer protocol 2 |
| Hudi | 1.2.0; table version 9; timeline layout 2; Copy-on-Write business table |
| Storage | LocalStack S3-compatible storage; not a production cloud validation |

All three Olist tables in this reference run are **unpartitioned**. The manual notebook also includes an update; it is a different workflow and its generated versions are not represented by the 3 → 5 → 4 reference here. Apache Paimon is not implemented in this lab, so no Paimon outputs are described.

The guides were checked against the saved `create.json`, `insert.json` and `delete.json`, the adapter code and primary documentation. The documentation work did not rerun the experiment. A saved file reference does not establish that its object remains available in a running LocalStack instance.

## Inspect your own run

1. Follow the [lab quick start](../README.md#quick-start) and execute the automated notebook in order.
2. Open the [metadata explorer](http://127.0.0.1:8765) and select **Refresh evidence**, then the delete stage and desired format.
3. Compare the metadata, raw-file viewer and physical inventory with the corresponding guide. Your run ID, snapshot IDs, instant times and filenames will differ.

The automated evidence lives under `local-lab/evidence/olist/`. `current.json` selects a run, and `runs/<run_id>/delete.json` contains the final saved snapshot. Evidence and source-derived outputs are intentionally excluded from Git. These Markdown guides contain selected structural values and aggregate counts, not a copy of the dataset or its raw metadata exports. See [data acquisition and license](../DATA_LICENSE.md).

For a local structural check, run this read-only command from `local-lab/`, replacing the run ID with yours:

```sh
jq '.formats[] | {format, root, validation, metadata, capture: (.raw_metadata | {candidate_count, inline_limit, note})}' \
  evidence/olist/runs/<run_id>/delete.json
```

## Capture limits

The raw-file viewer captures at most the newest 12 eligible metadata objects per format, with decoding limits. The inventory can list more files than the viewer decodes. In this run:

- Iceberg: all 11 eligible metadata objects were captured, including decoded Avro records.
- Delta Lake: all 6 eligible commit and checksum objects were captured.
- Hudi: 12 of 20 eligible main-table objects were captured at delete. The create snapshot supplies earlier table properties and index definitions. Auxiliary metadata-table contents and partition marker contents were not decoded.

Each guide distinguishes decoded contents, inventory-only observations and files that were not present. A system or metadata **table** exposed by an engine is a queryable view, not necessarily another physical file.

## What this comparison demonstrates

After the delete, saved inventories still contain older data files. Readers must interpret the format's committed state rather than read every Parquet file in the folder. The lab demonstrates that distinction; it does not benchmark performance, validate concurrent writers, prove crash recovery or test cross-engine compatibility.

When refreshing these guides, use one run consistently, recheck the selected state and arithmetic, preserve capture warnings, and update the version table. Never substitute a guessed file payload for an inventory-only object.

Check captured-property name coverage from the repository root after generating local automated evidence:

```sh
python3 local-lab/scripts/check_metadata_documentation.py
```

Pass `--run-id <run_id>` for a specific saved run, or `--evidence-root /path/to/olist` for another evidence location. This read-only check includes all three stages, embedded JSON schemas/statistics, table properties and captured SQL views. It checks for reference-table entries, not whether their explanations are semantically correct. Semantic review still requires the saved values and primary sources. It cannot validate properties in files whose contents were not captured.
