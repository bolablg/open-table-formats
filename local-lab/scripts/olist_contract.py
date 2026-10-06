"""Public Olist input contract and deterministic, explicitly simulated changes.

This module uses the standard library and never writes the source CSV.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLUMNS = ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
           "order_approved_at", "order_delivered_carrier_date",
           "order_delivered_customer_date", "order_estimated_delivery_date"]
TIMESTAMPS = COLUMNS[3:]
REQUIRED = COLUMNS[:4] + [COLUMNS[-1]]
SEED = "open-table-formats-lab-v1"
SOURCE_REFERENCE_SHA256 = "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"
STAGES = ["create", "insert", "update", "delete", "evolve"]
CORE_STAGES = ["create", "insert", "delete"]
# Used only to interpret already-saved runs. It is not an executable preset.
LEGACY100 = {"id": "legacy100", "label": "Synthetic 100-row exercise", "initial": 100, "insert": 10,
             "update_indices": list(range(5)), "delete_indices": [5, 6, 7],
             "stages": STAGES, "counts": [100, 110, 110, 107, 107], "sample_seed": SEED}


def article_config(initial_rows=3, insert_rows=2, delete_rows=1, sample_seed=SEED):
    for name, value in [("initial_rows", initial_rows), ("insert_rows", insert_rows), ("delete_rows", delete_rows)]:
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if initial_rows < 1:
        raise ValueError("initial_rows must be at least one")
    total = initial_rows + insert_rows
    if delete_rows > total:
        raise ValueError("delete_rows cannot exceed the rows present after insertion")
    if not isinstance(sample_seed, str) or not sample_seed.strip():
        raise ValueError("sample_seed must be a nonblank string")
    return {"id": "article", "label": f"Olist · {initial_rows} → {total} → {total-delete_rows}",
            "initial": initial_rows, "insert": insert_rows, "delete": delete_rows,
            "initial_rows": initial_rows, "insert_rows": insert_rows, "delete_rows": delete_rows,
            "sample_seed": sample_seed, "update_indices": [],
            "delete_indices": [(index+1) % total for index in range(delete_rows)],
            "stages": CORE_STAGES, "counts": [initial_rows, total, total-delete_rows]}


def stage_questions(config):
    return {
        "create": f"Which metadata makes the initial {config['initial']} orders a table?",
        "insert": f"How does each format publish {config['insert']} additional orders?",
        "update": f"What changes when {len(config['update_indices'])} estimated delivery dates are corrected?",
        "delete": f"Which metadata excludes {len(config['delete_indices'])} deleted {'order' if len(config['delete_indices']) == 1 else 'orders'} from the current state?",
        "evolve": "How is a new, explicitly synthetic column represented and populated?",
    }


def parse_timestamp(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def timestamp_text(value: datetime | None):
    return value.isoformat().replace("+00:00", "Z") if value else None


def file_sha256(path: str | Path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_selection(path: str | Path, configuration=None):
    config = configuration if configuration is not None else article_config()
    path = Path(path)
    digest = file_sha256(path)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError("CSV headers must exactly match the eight documented Olist columns")
        rows = list(reader)
    seen = set()
    nulls = Counter({column: 0 for column in COLUMNS})
    statuses = Counter()
    for row in rows:
        for column in COLUMNS:
            row[column] = row[column] or None
            nulls[column] += row[column] is None
        if any(row[column] is None for column in REQUIRED):
            raise ValueError("A required Olist value is missing")
        if row["order_id"] in seen:
            raise ValueError("Duplicate order keys in the source")
        seen.add(row["order_id"])
        statuses[row["order_status"]] += 1
        for column in TIMESTAMPS:
            parse_timestamp(row[column])  # Fail on invalid nonblank timestamps.
    sample_size = config["initial"] + config["insert"]
    if len(rows) < sample_size:
        raise ValueError(f"At least {sample_size} unique source orders are required for this configuration")
    rank = lambda row: (hashlib.sha256((config["sample_seed"] + ":" + row["order_id"]).encode("utf-8")).hexdigest(), row["order_id"])
    selected = sorted(rows, key=rank)[:sample_size]
    manifest = {
        "file_name": path.name, "sha256": digest,
        "matches_documented_source": digest == SOURCE_REFERENCE_SHA256,
        "row_count": len(rows), "columns": COLUMNS,
        "null_counts": dict(nulls), "status_counts": dict(sorted(statuses.items())),
        "seed": config["sample_seed"], "sampling": f"ascending (SHA256 UTF-8 seed + ':' + order_id, order_id); first {config['initial']} initial, next {config['insert']} inserts",
        "preset_id": config["id"], "preset_label": config["label"], "configuration": config,
        "selected_rows": sample_size,
        "initial_rows": config["initial"], "reserved_insert_rows": config["insert"],
        "update_sample_ranks": [index + 1 for index in config["update_indices"]],
        "delete_sample_ranks": [index + 1 for index in config["delete_indices"]],
        "stage_order": config["stages"], "expected_rows": config["counts"],
        "sample_sha256": hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "timezone_convention": "Parse offset-free source clocks using UTC for this lab; the source timezone is not established",
        "source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "license": "CC BY-NC-SA 4.0",
    }
    return selected, manifest


def typed_rows(rows):
    return [{column: parse_timestamp(row[column]) if column in TIMESTAMPS else row[column]
             for column in COLUMNS} for row in rows]


def channel(order_id):
    digest = hashlib.sha256(("sales-channel-v1:" + order_id).encode()).hexdigest()
    return ("WEB", "MOBILE", "STORE")[int(digest, 16) % 3]


def expected_rows(selected, stage, configuration=None):
    config = configuration if configuration is not None else article_config()
    stages = config["stages"]
    index = stages.index(stage)
    rows = typed_rows(selected[:config["initial"]] if stage == "create" else selected)
    update_keys = {selected[index]["order_id"] for index in config["update_indices"]}
    delete_keys = {selected[index]["order_id"] for index in config["delete_indices"]}
    if "update" in stages and index >= stages.index("update"):
        for row in rows:
            if row["order_id"] in update_keys:
                row["order_estimated_delivery_date"] += timedelta(days=1)
    if index >= stages.index("delete"):
        rows = [row for row in rows if row["order_id"] not in delete_keys]
    if "evolve" in stages and index >= stages.index("evolve"):
        for row in rows:
            row["sales_channel"] = channel(row["order_id"])
    return rows


def json_rows(rows):
    return [{key: timestamp_text(value) if isinstance(value, datetime) else value
             for key, value in row.items()} for row in sorted(rows, key=lambda r: r["order_id"])]


def row_diff(before, after):
    old = {row["order_id"]: row for row in before}
    new = {row["order_id"]: row for row in after}
    return {
        "inserted": [new[key] for key in sorted(new.keys() - old.keys())],
        "deleted": [old[key] for key in sorted(old.keys() - new.keys())],
        "updated": [{"order_id": key, "before": old[key], "after": new[key],
                     "changed_columns": [c for c in new[key] if c not in old[key] or new[key][c] != old[key][c]]}
                    for key in sorted(new.keys() & old.keys()) if new[key] != old[key]],
    }
