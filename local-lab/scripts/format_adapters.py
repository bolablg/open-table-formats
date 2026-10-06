"""Format-specific writes and metadata inspection for Lab 1."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from pyspark.sql import DataFrame, SparkSession

from lab_common import BASE_COLUMNS, DELETE_IDS, EVOLVED_COLUMNS, UPDATE_IDS, collect_rows, list_objects


class IcebergAdapter:
    name = "iceberg"

    def __init__(self, spark: SparkSession, bucket: str) -> None:
        self.spark = spark
        self.table = "iceberg.lab.orders"
        self.root = f"s3a://{bucket}/warehouse/iceberg/lab/orders"

    def create(self, frame: DataFrame) -> None:
        frame.createOrReplaceTempView("initial_orders")
        self.spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.lab")
        self.spark.sql(f"DROP TABLE IF EXISTS {self.table}")
        self.spark.sql(
            f"""
            CREATE TABLE {self.table}
            USING iceberg
            PARTITIONED BY (days(order_timestamp))
            TBLPROPERTIES (
              'format-version'='2',
              'write.update.mode'='copy-on-write',
              'write.delete.mode'='copy-on-write',
              'write.merge.mode'='copy-on-write'
            )
            AS SELECT * FROM initial_orders
            """
        )

    def insert(self, frame: DataFrame) -> None:
        frame.createOrReplaceTempView("insert_orders")
        self.spark.sql(f"INSERT INTO {self.table} SELECT * FROM insert_orders")

    def update(self, _frame: DataFrame) -> None:
        ids = ",".join(map(str, UPDATE_IDS))
        self.spark.sql(f"UPDATE {self.table} SET status='SHIPPED' WHERE order_id IN ({ids})")

    def delete(self, _frame: DataFrame) -> None:
        ids = ",".join(map(str, DELETE_IDS))
        self.spark.sql(f"DELETE FROM {self.table} WHERE order_id IN ({ids})")

    def evolve(self, _frame: DataFrame) -> None:
        self.spark.sql(f"ALTER TABLE {self.table} ADD COLUMN sales_channel STRING")
        self.spark.sql(
            f"""
            UPDATE {self.table}
            SET sales_channel = CASE pmod(order_id, 3)
              WHEN 0 THEN 'WEB' WHEN 1 THEN 'MOBILE' ELSE 'STORE' END
            """
        )

    def read(self) -> DataFrame:
        return self.spark.table(self.table)

    def inspect(self) -> dict[str, Any]:
        tables = {}
        for suffix in ("history", "snapshots", "manifests"):
            try:
                tables[suffix] = collect_rows(self.spark.table(f"{self.table}.{suffix}"), limit=40)
            except Exception as exc:
                tables[suffix] = {"error": str(exc).splitlines()[0]}
        try:
            files = self.spark.table(f"{self.table}.files")
            tables["files"] = {
                "row_count": files.count(),
                "sample": collect_rows(files, limit=12),
            }
        except Exception as exc:
            tables["files"] = {"error": str(exc).splitlines()[0]}
        metadata_json = [
            item for item in list_objects(self.spark, f"{self.root}/metadata")
            if item["path"].endswith(".metadata.json")
        ]
        return {
            "what_to_notice": "Snapshots point to manifest lists; manifests enumerate the data files in a snapshot.",
            "system_tables": tables,
            "metadata_json_files": [item["path"] for item in metadata_json],
        }


class DeltaAdapter:
    name = "delta"

    def __init__(self, spark: SparkSession, bucket: str) -> None:
        self.spark = spark
        self.root = f"s3a://{bucket}/warehouse/delta/orders"
        self.identifier = f"delta.`{self.root}`"

    def create(self, frame: DataFrame) -> None:
        (
            frame.write.format("delta")
            .option("delta.checkpointInterval", "5")
            .mode("overwrite")
            .save(self.root)
        )

    def insert(self, frame: DataFrame) -> None:
        frame.write.format("delta").mode("append").save(self.root)

    def update(self, _frame: DataFrame) -> None:
        ids = ",".join(map(str, UPDATE_IDS))
        self.spark.sql(f"UPDATE {self.identifier} SET status='SHIPPED' WHERE order_id IN ({ids})")

    def delete(self, _frame: DataFrame) -> None:
        ids = ",".join(map(str, DELETE_IDS))
        self.spark.sql(f"DELETE FROM {self.identifier} WHERE order_id IN ({ids})")

    def evolve(self, _frame: DataFrame) -> None:
        self.spark.sql(f"ALTER TABLE {self.identifier} ADD COLUMNS (sales_channel STRING)")
        self.spark.sql(
            f"""
            UPDATE {self.identifier}
            SET sales_channel = CASE pmod(order_id, 3)
              WHEN 0 THEN 'WEB' WHEN 1 THEN 'MOBILE' ELSE 'STORE' END
            """
        )

    def read(self) -> DataFrame:
        return self.spark.read.format("delta").load(self.root)

    def inspect(self) -> dict[str, Any]:
        log_objects = list_objects(self.spark, f"{self.root}/_delta_log")
        json_logs = sorted(item["path"] for item in log_objects if item["path"].endswith(".json"))
        action_counts: Counter[str] = Counter()
        versions: list[dict[str, Any]] = []
        for path in json_logs:
            actions = self.spark.read.json(path)
            counts: Counter[str] = Counter()
            for row in actions.collect():
                payload = row.asDict(recursive=True)
                for action in ("commitInfo", "metaData", "protocol", "add", "remove", "txn", "cdc"):
                    if payload.get(action) is not None:
                        counts[action] += 1
                        action_counts[action] += 1
            versions.append({"log_file": path, "actions": dict(counts)})
        try:
            history = collect_rows(self.spark.sql(f"DESCRIBE HISTORY {self.identifier}"))
        except Exception as exc:
            history = [{"error": str(exc).splitlines()[0]}]
        return {
            "what_to_notice": "Each JSON commit records actions such as add, remove, metadata, and protocol changes.",
            "history": history,
            "versions": versions,
            "total_action_counts": dict(action_counts),
            "checkpoint_files": [
                item["path"] for item in log_objects if ".checkpoint." in item["path"]
            ],
        }


class HudiAdapter:
    name = "hudi"

    def __init__(self, spark: SparkSession, bucket: str) -> None:
        self.spark = spark
        self.root = f"s3a://{bucket}/warehouse/hudi/orders"
        self.base_options = {
            "hoodie.table.name": "orders",
            "hoodie.datasource.write.recordkey.field": "order_id",
            "hoodie.datasource.write.precombine.field": "order_timestamp",
            "hoodie.datasource.write.partitionpath.field": "country",
            "hoodie.datasource.write.hive_style_partitioning": "true",
            "hoodie.datasource.write.table.type": "COPY_ON_WRITE",
            "hoodie.datasource.write.reconcile.schema": "true",
            "hoodie.schema.on.read.enable": "true",
            "hoodie.clean.automatic": "false",
            "hoodie.metadata.enable": "true",
        }

    def _write(self, frame: DataFrame, operation: str, mode: str = "append") -> None:
        options = {**self.base_options, "hoodie.datasource.write.operation": operation}
        frame.write.format("hudi").options(**options).mode(mode).save(self.root)

    def create(self, frame: DataFrame) -> None:
        self._write(frame, "bulk_insert", "overwrite")

    def insert(self, frame: DataFrame) -> None:
        self._write(frame, "insert")

    def update(self, frame: DataFrame) -> None:
        self._write(frame, "upsert")

    def delete(self, frame: DataFrame) -> None:
        self._write(frame, "delete")

    def evolve(self, frame: DataFrame) -> None:
        self._write(frame, "upsert")

    def read(self) -> DataFrame:
        return self.spark.read.format("hudi").load(self.root)

    def inspect(self) -> dict[str, Any]:
        objects = list_objects(self.spark, self.root)
        timeline = [
            item for item in objects
            if "/.hoodie/timeline/" in item["path"]
            or (
                "/.hoodie/" in item["path"]
                and any(token in item["path"] for token in (".commit", ".deltacommit", ".replacecommit"))
            )
        ]
        parquet_files = [item for item in objects if item["path"].endswith(".parquet")]
        log_files = [item for item in objects if ".log." in item["path"]]
        return {
            "what_to_notice": "The active timeline records completed instants; Copy-on-Write commits replace Parquet base files.",
            "table_type": "COPY_ON_WRITE",
            "timeline_files": [item["path"] for item in timeline],
            "parquet_file_count": len(parquet_files),
            "merge_on_read_log_file_count": len(log_files),
            "merge_on_read_note": "Zero log files are expected here because this lab intentionally uses Copy-on-Write.",
        }


def adapters(spark: SparkSession, bucket: str) -> list[IcebergAdapter | DeltaAdapter | HudiAdapter]:
    return [IcebergAdapter(spark, bucket), DeltaAdapter(spark, bucket), HudiAdapter(spark, bucket)]
