"""Shared Spark, storage, and comparison helpers for Lab 1."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


BASE_COLUMNS = [
    "order_id",
    "customer_id",
    "order_timestamp",
    "country",
    "product_id",
    "quantity",
    "unit_price",
    "total_amount",
    "status",
]
EVOLVED_COLUMNS = [*BASE_COLUMNS, "sales_channel"]
UPDATE_IDS = [1001, 1002, 1003, 1004, 1005]
DELETE_IDS = [1006, 1007, 1008]


ORDER_SCHEMA = StructType(
    [
        StructField("order_id", LongType(), False),
        StructField("customer_id", StringType(), False),
        StructField("order_timestamp", TimestampType(), False),
        StructField("country", StringType(), False),
        StructField("product_id", StringType(), False),
        StructField("quantity", IntegerType(), False),
        StructField("unit_price", DecimalType(12, 2), False),
        StructField("total_amount", DecimalType(14, 2), False),
        StructField("status", StringType(), False),
    ]
)


def build_spark() -> SparkSession:
    endpoint = os.environ.get("S3_ENDPOINT", "http://s3:4566")
    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket = os.environ.get("S3_BUCKET", "lakehouse-lab")
    return (
        SparkSession.builder.appName("open-table-formats-lab-1")
        .config(
            "spark.sql.extensions",
            ",".join(
                [
                    "io.delta.sql.DeltaSparkSessionExtension",
                    "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
                ]
            ),
        )
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "hadoop")
        .config("spark.sql.catalog.iceberg.warehouse", f"s3a://{bucket}/warehouse/iceberg")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        .config("spark.hadoop.fs.s3a.access.key", os.environ.get("AWS_ACCESS_KEY_ID", "test"))
        .config("spark.hadoop.fs.s3a.secret.key", os.environ.get("AWS_SECRET_ACCESS_KEY", "test"))
        .config("spark.hadoop.fs.s3a.endpoint.region", region)
        .config("spark.hadoop.fs.s3a.change.detection.mode", "none")
        .config("spark.hadoop.fs.s3a.committer.name", "directory")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .getOrCreate()
    )


def make_insert_rows(spark: SparkSession) -> DataFrame:
    start = datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)
    values = []
    countries = ("US", "CA", "GB", "DE", "NG")
    for offset in range(10):
        price = Decimal("18.25") + Decimal(offset * 4)
        quantity = 1 + (offset % 3)
        values.append(
            (
                1101 + offset,
                f"C-{260 + offset:03d}",
                start + timedelta(hours=offset * 3),
                countries[offset % len(countries)],
                f"P-{700 + offset}",
                quantity,
                price,
                price * quantity,
                "PAID" if offset % 2 == 0 else "PENDING",
            )
        )
    return spark.createDataFrame(values, ORDER_SCHEMA)


def canonical_rows(df: DataFrame, columns: list[str]) -> list[tuple[Any, ...]]:
    return [
        tuple(jsonable(row[column]) for column in columns)
        for row in df.select(*columns).orderBy("order_id").collect()
    ]


def assert_same(actual: DataFrame, expected: DataFrame, columns: list[str], label: str) -> dict[str, Any]:
    actual_rows = canonical_rows(actual, columns)
    expected_rows = canonical_rows(expected, columns)
    if actual_rows != expected_rows:
        actual_set, expected_set = set(actual_rows), set(expected_rows)
        raise AssertionError(
            f"{label} differs from expected: "
            f"missing={list(expected_set - actual_set)[:3]}, "
            f"unexpected={list(actual_set - expected_set)[:3]}"
        )
    summary = actual.agg(
        F.count("*").alias("row_count"),
        F.sum("total_amount").alias("total_amount"),
    ).first()
    return {
        "matches_expected": True,
        "row_count": summary.row_count,
        "total_amount": str(summary.total_amount),
        "columns": columns,
    }


def list_objects(spark: SparkSession, uri: str) -> list[dict[str, Any]]:
    jvm = spark.sparkContext._jvm
    path = jvm.org.apache.hadoop.fs.Path(uri)
    fs = path.getFileSystem(spark.sparkContext._jsc.hadoopConfiguration())
    if not fs.exists(path):
        return []
    iterator = fs.listFiles(path, True)
    objects: list[dict[str, Any]] = []
    while iterator.hasNext():
        status = iterator.next()
        objects.append(
            {
                "path": status.getPath().toString(),
                "size_bytes": status.getLen(),
                "modified_ms": status.getModificationTime(),
            }
        )
    return sorted(objects, key=lambda item: item["path"])


def inventory_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, list[str]]:
    previous = {item["path"]: item["size_bytes"] for item in before}
    current = {item["path"]: item["size_bytes"] for item in after}
    return {
        "added": sorted(current.keys() - previous.keys()),
        "removed": sorted(previous.keys() - current.keys()),
        "size_changed": sorted(
            path for path in current.keys() & previous.keys() if current[path] != previous[path]
        ),
    }


def collect_rows(df: DataFrame, limit: int = 200) -> list[dict[str, Any]]:
    return [jsonable(row.asDict(recursive=True)) for row in df.limit(limit).collect()]


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return value
