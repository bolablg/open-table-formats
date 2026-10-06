"""One shared stage API for the notebook, CLI and generated evidence."""
from __future__ import annotations

import html
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from lab_common import build_spark, jsonable, list_objects
from olist_adapters import olist_adapters
from evidence_views import metadata_summary
from olist_contract import COLUMNS, LEGACY100, SEED, article_config, expected_rows, file_sha256, json_rows, row_diff, source_selection, stage_questions, typed_rows

RUN_PATTERN = r"olist_(?:(?:tiny|article_[1-9][0-9]*_[0-9]+_[0-9]+)_)?[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp_" + uuid.uuid4().hex[:8])
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def inventory_diff(before, after):
    old = {item["path"]: item for item in before}
    new = {item["path"]: item for item in after}
    return {
        "added": [new[key] for key in sorted(new.keys() - old.keys())],
        "removed": [old[key] for key in sorted(old.keys() - new.keys())],
        "changed": [{"before": old[key], "after": new[key]} for key in sorted(new.keys() & old.keys())
                    if (old[key]["size_bytes"], old[key]["modified_ms"]) != (new[key]["size_bytes"], new[key]["modified_ms"])],
        "change_basis": "Object presence, size and modification time; physical retention can outlive logical deletion",
    }


def metadata_files(spark, adapter, inventory):
    """Read actual metadata text/Avro, never business Parquet as metadata."""
    candidates = [item for item in inventory if
                  (adapter.name == "iceberg" and "/metadata/" in item["path"]) or
                  (adapter.name == "delta" and "/_delta_log/" in item["path"]) or
                  (adapter.name == "hudi" and "/.hoodie/" in item["path"] and "/metadata/" not in item["path"])]
    candidates.sort(key=lambda item: (item["modified_ms"], item["path"]), reverse=True)
    result = []
    jvm = spark.sparkContext._jvm
    conf = spark.sparkContext._jsc.hadoopConfiguration()
    for item in candidates[:12]:
        record = dict(item)
        path = jvm.org.apache.hadoop.fs.Path(item["path"])
        fs = path.getFileSystem(conf)
        stream = None
        try:
            if item["size_bytes"] > 300000:
                record.update({"encoding": "not decoded", "note": "File exceeds the 300 KB inline limit; inventory and inspection command remain available"})
            elif item["path"].endswith(".parquet"):
                frame = spark.read.parquet(item["path"])
                record.update({"encoding": "Parquet records", "records": jsonable([row.asDict(recursive=True) for row in frame.limit(100).collect()]), "truncated": frame.count() > 100})
            else:
                stream = fs.open(path)
                header = bytes(stream.read() for _ in range(min(4, item["size_bytes"])))
                stream.close()
                stream = fs.open(path)
                if header == b"Obj\x01":
                    reader = jvm.org.apache.avro.file.DataFileStream(stream, jvm.org.apache.avro.generic.GenericDatumReader())
                    records = []
                    while reader.hasNext() and len(records) < 100:
                        records.append(json.loads(str(reader.next())))
                    record.update({"encoding": "Avro records", "records": records, "truncated": bool(reader.hasNext())})
                    reader.close()
                else:
                    reader = jvm.java.io.BufferedReader(jvm.java.io.InputStreamReader(stream, "UTF-8"))
                    lines = []
                    line = reader.readLine()
                    while line is not None:
                        lines.append(str(line))
                        line = reader.readLine()
                    record.update({"encoding": "UTF-8 text", "text": "\n".join(lines)})
                    reader.close()
        except Exception as error:
            record.update({"encoding": "not decoded", "inspection_error": str(error).splitlines()[0][:400]})
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
        result.append(record)
    return {"files": result, "candidate_count": len(candidates), "inline_limit": 12,
            "note": "Actual generated files; newest twelve metadata objects are shown, with explicit decoding limits"}


class OlistLab:
    def __init__(self, run_id, spark=None):
        if not re.fullmatch(RUN_PATTERN, run_id):
            raise ValueError("Invalid Olist run ID")
        endpoint = os.environ.get("S3_ENDPOINT", "http://s3:4566")
        if endpoint not in {"http://s3:4566", "http://127.0.0.1:4566", "http://localhost:4566"}:
            raise ValueError("This lab only permits the local S3 emulator")
        self.run_id = run_id
        self.output = Path(os.environ.get("OLIST_EVIDENCE_DIR", "/workspace/evidence/olist"))
        self.run_dir = self.output / "runs" / run_id
        self.manifest_path = self.run_dir / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())
        self.preset_id = self.manifest.get("preset_id", "legacy100")
        self.is_legacy = self.manifest.get("evidence_schema_version", 0) < 4
        if "configuration" in self.manifest:
            saved = self.manifest["configuration"]
            self.config = article_config(**{name: saved[name] for name in ["initial_rows", "insert_rows", "delete_rows", "sample_seed"]})
        else:
            self.config = article_config() if self.preset_id == "tiny" else LEGACY100
        self.stages = self.config["stages"]
        self.source_path = os.environ.get("OLIST_CSV_PATH", "/source/olist_orders_dataset.csv")
        self.selected, source = source_selection(self.source_path, self.config)
        if source["sha256"] != self.manifest["source"]["sha256"]:
            raise ValueError("Source CSV changed since this run began; start a new run")
        if source["sample_sha256"] != self.manifest["source"]["sample_sha256"]:
            raise ValueError("Recorded sampling configuration changed; start a new isolated run")
        self.spark = spark or build_spark()
        self.spark.sparkContext.setLogLevel("WARN")
        self.bucket = os.environ.get("S3_BUCKET", "lakehouse-lab")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket):
            raise ValueError("Invalid local S3 bucket name")
        self.adapters = olist_adapters(self.spark, self.bucket, run_id)

    @classmethod
    def start(cls, spark=None, initial_rows=3, insert_rows=2, delete_rows=1, sample_seed=SEED):
        config = article_config(initial_rows, insert_rows, delete_rows, sample_seed)
        source_path = os.environ.get("OLIST_CSV_PATH", "/source/olist_orders_dataset.csv")
        _, source = source_selection(source_path, config)
        run_id = f"olist_article_{initial_rows}_{insert_rows}_{delete_rows}_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        output = Path(os.environ.get("OLIST_EVIDENCE_DIR", "/workspace/evidence/olist"))
        manifest = {"run_id": run_id, "created_at": utc_now(), "updated_at": utc_now(),
                    "evidence_schema_version": 4, "preset_id": "article", "preset_label": config["label"], "configuration": config,
                    "status": "ready", "completed_stages": [], "source": source,
                    "stages": [{"id": stage, "expected_rows": config["counts"][index], "question": stage_questions(config)[stage]} for index, stage in enumerate(config["stages"])],
                    "scope": "Single-writer create/insert/delete correctness and metadata experiment; controlled deletion; no benchmark or interoperability proof"}
        atomic_json(output / "runs" / run_id / "manifest.json", manifest)
        atomic_json(output / "current.json", {"run_id": run_id})
        return cls(run_id, spark=spark)

    @classmethod
    def resume(cls, run_id=None):
        output = Path(os.environ.get("OLIST_EVIDENCE_DIR", "/workspace/evidence/olist"))
        if run_id is None:
            run_id = json.loads((output / "current.json").read_text())["run_id"]
        return cls(run_id)

    def _save_manifest(self):
        self.manifest["updated_at"] = utc_now()
        atomic_json(self.manifest_path, self.manifest)

    def _frame(self, rows):
        from pyspark.sql.types import StringType, StructField, StructType, TimestampType
        from olist_contract import REQUIRED, TIMESTAMPS
        columns = COLUMNS + (["sales_channel"] if rows and "sales_channel" in rows[0] else [])
        schema = StructType([StructField(column, TimestampType() if column in TIMESTAMPS else StringType(), column not in REQUIRED) for column in columns])
        return self.spark.createDataFrame(rows, schema)

    def stage(self, stage):
        if self.is_legacy:
            raise ValueError("Earlier runs are read-only; start a new Olist walkthrough")
        if stage not in self.stages:
            raise ValueError(f"Stage {stage} is not part of the automated walkthrough; its core sequence is create, insert, delete")
        index = len(self.manifest["completed_stages"])
        if self.manifest["status"] in {"failed", "reset", "completed"} or index >= len(self.stages) or self.stages[index] != stage:
            raise ValueError("Stage out of sequence or run closed. Start a new run to repeat the walkthrough")
        self.manifest.update({"status": "running", "active_stage": stage})
        self._save_manifest()
        try:
            if file_sha256(self.source_path) != self.manifest["source"]["sha256"]:
                raise ValueError("Source CSV changed during this run; no operation was executed")
            expected = expected_rows(self.selected, stage, self.config)
            columns = COLUMNS
            expected_json = json_rows(expected)
            before_payload = json.loads((self.run_dir / (self.stages[index-1] + ".json")).read_text()) if index else None
            payload = {"run_id": self.run_id, "preset_id": self.preset_id, "preset_label": self.config["label"],
                       "configuration": self.config, "write_action": "no-op" if stage != "create" and self.config[stage] == 0 else stage,
                       "stage": stage, "question": stage_questions(self.config)[stage],
                       "started_at": utc_now(), "expected_rows": self.config["counts"][index],
                       "expected_schema": columns, "formats": [], "evidence_kind": "saved operation snapshot"}
            for adapter in self.adapters:
                if stage == "create":
                    adapter.create(self._frame(expected))
                elif stage == "insert":
                    if self.config["insert"]:
                        adapter.insert(self._frame(typed_rows(self.selected[self.config["initial"]:])))
                elif stage == "delete":
                    keys = [self.selected[index]["order_id"] for index in self.config["delete_indices"]]
                    if keys:
                        if adapter.name == "hudi":
                            previous = expected_rows(self.selected, self.stages[index-1], self.config)
                            adapter.delete(self._frame([row for row in previous if row["order_id"] in keys]))
                        else:
                            adapter.delete_keys(keys)
                frame = adapter.read().select(*columns)
                actual = jsonable([row.asDict(recursive=True) for row in frame.orderBy("order_id").collect()])
                if actual != expected_json:
                    raise AssertionError(f"{adapter.name}/{stage}: business values differ from expected state")
                inventory = list_objects(self.spark, adapter.root)
                previous = next((item for item in before_payload["formats"] if item["format"] == adapter.name), None) if before_payload else None
                metadata = adapter.inspect()
                raw = metadata_files(self.spark, adapter, inventory)
                payload["formats"].append({"format": adapter.name, "root": adapter.root,
                    "validation": {"status": "PASS", "matches_expected": True, "row_count": len(actual),
                                   "unique_keys": len({row["order_id"] for row in actual}), "business_columns": columns},
                    "rows": actual, "schema": frame.schema.jsonValue(),
                    "row_changes": row_diff(previous["rows"] if previous else [], actual),
                    "metadata": metadata, "raw_metadata": raw, "inventory": inventory,
                    "file_changes": inventory_diff(previous["inventory"] if previous else [], inventory),
                    "reader_language": "python" if adapter.name == "hudi" else "sql",
                    "reader_command": f'lab.spark.read.format("hudi").load("{adapter.root}").show(truncate=False)' if adapter.name == "hudi" else f"SELECT * FROM {adapter.table if adapter.name == 'iceberg' else adapter.identifier}"})
            payload.update({"captured_at": utc_now(), "validation_status": "PASS",
                            "runtime": {"spark": self.spark.version, "timezone": self.spark.conf.get("spark.sql.session.timeZone")}})
            atomic_json(self.run_dir / (stage + ".json"), payload)
            self.manifest["completed_stages"].append(stage)
            self.manifest.update({"status": "completed" if stage == self.stages[-1] else "ready", "active_stage": None,
                                  "latest_snapshot_at": payload["captured_at"]})
            self._save_manifest()
            return payload
        except Exception as error:
            self.manifest.update({"status": "failed", "failed_stage": stage, "error": str(error)[:1500]})
            self._save_manifest()
            raise

    def reset(self, confirm_run_id):
        """Delete only this run's disposable objects; retain its saved evidence."""
        if confirm_run_id != self.run_id:
            raise ValueError("Reset requires the exact current run ID")
        if self.is_legacy:
            raise ValueError("Earlier runs and their resources are read-only")
        prefix = f"s3a://{self.bucket}/olist/runs/{self.run_id}"
        for adapter in self.adapters:
            if not adapter.root.startswith(prefix + "/"):
                raise ValueError("Refusing reset outside this Olist run")
        path = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(prefix)
        fs = path.getFileSystem(self.spark.sparkContext._jsc.hadoopConfiguration())
        fs.delete(path, True)
        self.manifest.update({"status": "reset", "resources_deleted_at": utc_now(), "active_stage": None})
        self._save_manifest()

    def source_summary(self):
        from IPython.display import HTML
        return HTML("<h3>Recorded source and sampling contract</h3><pre>" + html.escape(json.dumps(self.manifest, indent=2)) + "</pre>")

    def show(self, payload):
        from IPython.display import HTML, display
        cells = "".join(f"<tr><td>{item['format']}</td><td>{item['validation']['row_count']}</td><td>{item['validation']['status']}</td><td>{len(item['row_changes']['inserted'])}</td><td>{len(item['row_changes']['updated'])}</td><td>{len(item['row_changes']['deleted'])}</td><td>{len(item['file_changes']['added'])}</td><td>{len(item['file_changes']['removed'])}</td><td>{len(item['file_changes']['changed'])}</td></tr>" for item in payload["formats"])
        display(HTML(f"<h3>{html.escape(payload['question'])}</h3><p>{html.escape(self.config['label'])}. Saved snapshot {payload['captured_at']}; expected {payload['expected_rows']} rows. Write action: {payload['write_action']}. Row changes describe business values; file changes include retained history and auxiliary metadata.</p><table><tr><th>Format</th><th>Rows</th><th>Business values</th><th>Introduced</th><th>Updated</th><th>Deleted</th><th>Files added</th><th>Removed</th><th>Changed</th></tr>{cells}</table>"))
        if self.config["counts"][1] <= 20:
            display(HTML("<details open><summary>Verified business rows (identical across all three formats)</summary><pre>" + html.escape(json.dumps(payload["formats"][0]["rows"], indent=2)) + "</pre></details>"))

    def show_format(self, payload, name):
        from IPython.display import HTML, display
        item = next(item for item in payload["formats"] if item["format"] == name)
        sections = {"Summary derived from captured metadata": metadata_summary(item),
                    "Schema": item["schema"], "Row changes": item["row_changes"],
                    "Metadata interfaces": item["metadata"], "Actual metadata files": item["raw_metadata"],
                    "Object inventory changes": item["file_changes"]}
        markup = f"<h3>{name}: {html.escape(item['metadata']['what_to_notice'])}</h3><p>Reader command: <code>{html.escape(item['reader_command'])}</code></p>"
        markup += "".join("<details><summary>" + heading + "</summary><pre>" + html.escape(json.dumps(value, indent=2)) + "</pre></details>" for heading, value in sections.items())
        display(HTML(markup))
