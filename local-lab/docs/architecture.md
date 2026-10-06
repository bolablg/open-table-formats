# Synthetic orders exercise

## Question

If Iceberg, Delta Lake, and Hudi receive the same rows and the same sequence of changes, how do they preserve table state on object storage?

## Controlled variables

- One deterministic 100-row orders CSV.
- One Spark 3.5 process and one local S3-compatible service.
- The same business schema and the same five operations: create, insert, update, delete, and schema evolution.
- Independent storage prefixes so that no format can manage another format's files.
- Hudi uses Copy-on-Write; Iceberg uses format version 2 with copy-on-write row-level changes.

## Flow

```text
deterministic generator
        |
        v
S3-compatible raw/orders/orders.csv
        |
        v
Apache Spark
   |             |             |
   v             v             v
Iceberg        Delta          Hudi COW
snapshots +    ordered log    active timeline +
manifests      actions        file-group state
   |             |             |
   +-------------+-------------+
                 |
     row-by-row equality checks
                 |
       evidence/lab1-report.*
```

## Operation sequence

1. Create each table from 100 orders.
2. Insert 10 new orders (110 rows).
3. Update five known order IDs from `PENDING` to `SHIPPED` (110 rows).
4. Delete three known order IDs (107 rows).
5. Add and populate `sales_channel` (107 rows, ten business columns).

After every operation, the runner orders all business rows by `order_id` and compares every value. It also snapshots each format's object inventory and inspects its metadata interfaces.

## What the inspection means

| Format | Evidence inspected | Main idea |
| --- | --- | --- |
| Iceberg | `history`, `snapshots`, `manifests`, and `files` metadata tables | A current snapshot selects a manifest list; manifests select data files. |
| Delta Lake | `_delta_log` JSON actions, checkpoints, and `DESCRIBE HISTORY` | An ordered transaction log applies `add`, `remove`, metadata, and protocol actions. |
| Hudi | `.hoodie` active timeline, Parquet file count, and table type | Timeline instants coordinate changes to file groups; Copy-on-Write replaces base files. |

## Scope

It is not a benchmark and does not test concurrent writers, crash recovery, catalog interoperability, streaming ingestion, maintenance economics, or cloud service integrations. Hudi Merge-on-Read is deliberately excluded; its log files and read-time merge behavior belong in a streaming-focused lab.
