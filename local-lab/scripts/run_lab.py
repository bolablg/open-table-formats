"""Run Lab 1: identical table mutations, different metadata systems."""

from __future__ import annotations

import json
import os
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from format_adapters import adapters
from lab_common import (
    BASE_COLUMNS,
    DELETE_IDS,
    EVOLVED_COLUMNS,
    ORDER_SCHEMA,
    UPDATE_IDS,
    assert_same,
    build_spark,
    inventory_delta,
    list_objects,
    make_insert_rows,
)
from reporting import write_reports


def capture_stage(
    stage: str,
    formats: list[Any],
    expected: DataFrame,
    columns: list[str],
    previous: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    entries = []
    for table_format in formats:
        inventory = list_objects(table_format.spark, table_format.root)
        validation = assert_same(table_format.read(), expected, columns, f"{table_format.name}/{stage}")
        entries.append(
            {
                "format": table_format.name,
                "validation": validation,
                "object_count": len(inventory),
                "object_delta": inventory_delta(previous.get(table_format.name, []), inventory),
                "metadata": table_format.inspect(),
            }
        )
        previous[table_format.name] = inventory
    return {
        "stage": stage,
        "expected_row_count": expected.count(),
        "formats": entries,
    }


def main() -> None:
    bucket = os.environ.get("S3_BUCKET", "lakehouse-lab")
    raw_path = f"s3a://{bucket}/raw/orders/orders.csv"
    evidence_dir = os.environ.get("EVIDENCE_DIR", "/workspace/evidence")

    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        initial = (
            spark.read.option("header", "true")
            .option("timestampFormat", "yyyy-MM-dd'T'HH:mm:ssX")
            .schema(ORDER_SCHEMA)
            .csv(raw_path)
        )
        if initial.count() != 100:
            raise AssertionError(f"Expected 100 initial rows, found {initial.count()}")

        table_formats = adapters(spark, bucket)
        previous: dict[str, list[dict[str, Any]]] = {}
        stages: list[dict[str, Any]] = []

        for table_format in table_formats:
            table_format.create(initial)
        expected = initial
        stages.append(capture_stage("create", table_formats, expected, BASE_COLUMNS, previous))

        inserted = make_insert_rows(spark)
        for table_format in table_formats:
            table_format.insert(inserted)
        expected = expected.unionByName(inserted)
        stages.append(capture_stage("insert 10 rows", table_formats, expected, BASE_COLUMNS, previous))

        expected = expected.withColumn(
            "status",
            F.when(F.col("order_id").isin(*UPDATE_IDS), F.lit("SHIPPED")).otherwise(F.col("status")),
        )
        updated_rows = expected.filter(F.col("order_id").isin(*UPDATE_IDS))
        for table_format in table_formats:
            table_format.update(updated_rows)
        stages.append(capture_stage("update 5 rows", table_formats, expected, BASE_COLUMNS, previous))

        rows_to_delete = expected.filter(F.col("order_id").isin(*DELETE_IDS))
        for table_format in table_formats:
            table_format.delete(rows_to_delete)
        expected = expected.filter(~F.col("order_id").isin(*DELETE_IDS))
        stages.append(capture_stage("delete 3 rows", table_formats, expected, BASE_COLUMNS, previous))

        expected = expected.withColumn(
            "sales_channel",
            F.when(F.pmod(F.col("order_id"), F.lit(3)) == 0, F.lit("WEB"))
            .when(F.pmod(F.col("order_id"), F.lit(3)) == 1, F.lit("MOBILE"))
            .otherwise(F.lit("STORE")),
        )
        for table_format in table_formats:
            table_format.evolve(expected)
        stages.append(capture_stage("add sales_channel", table_formats, expected, EVOLVED_COLUMNS, previous))

        payload = {
            "status": "PASS",
            "raw_source": raw_path,
            "initial_row_count": 100,
            "final_row_count": expected.count(),
            "operations": ["create", "insert", "update", "delete", "schema evolution"],
            "stages": stages,
            "scope_note": "Correctness and metadata inspection only; not a performance benchmark.",
        }
        json_path, markdown_path = write_reports(payload, evidence_dir)
        compact = {
            "status": payload["status"],
            "initial_row_count": payload["initial_row_count"],
            "final_row_count": payload["final_row_count"],
            "stages": [
                {
                    "stage": stage["stage"],
                    "row_counts": {
                        item["format"]: item["validation"]["row_count"]
                        for item in stage["formats"]
                    },
                }
                for stage in stages
            ],
            "reports": [str(json_path), str(markdown_path)],
        }
        print("\nOPEN_TABLE_FORMAT_LAB_RESULT")
        print(json.dumps(compact, indent=2, sort_keys=True))
        print("LAB_STATUS=PASS")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
