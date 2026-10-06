"""Readable summaries derived only from captured metadata, without live queries."""
import json
from pathlib import PurePosixPath


def metadata_summary(item):
    metadata = item["metadata"]
    raw = item["raw_metadata"]["files"]
    if item["format"] == "iceberg":
        documents = []
        for file in raw:
            if file["path"].endswith(".metadata.json") and "text" in file:
                documents.append(json.loads(file["text"]))
        current = max(documents, key=lambda value: value.get("last-updated-ms", 0)) if documents else {}
        return {"Current snapshot ID": current.get("current-snapshot-id", "Not captured"),
                "Current schema ID": current.get("current-schema-id", "Not captured"),
                "Active data files": metadata.get("system_tables", {}).get("files", {}).get("row_count", "Not captured"),
                "Partition spec ID": current.get("default-spec-id", "Not captured")}
    if item["format"] == "delta":
        versions = metadata.get("versions", [])
        latest = versions[-1] if versions else {}
        filename = PurePosixPath(latest.get("log_file", "")).stem
        return {"Latest log version": int(filename) if filename.isdigit() else "Not captured",
                "Latest commit actions": latest.get("actions", {}),
                "Captured checkpoints": len(metadata.get("checkpoint_files", []))}
    main_timeline = item["root"] + "/.hoodie/timeline/"
    completed = sorted(path for path in metadata.get("timeline_files", []) if path.startswith(main_timeline)
                       if path.endswith((".commit", ".deltacommit", ".replacecommit")))
    latest = next((file for file in raw if completed and file["path"] == completed[-1]), {})
    record = (latest.get("records") or [{}])[0]
    return {"Table type": metadata.get("table_type", "Not captured"),
            "Completed table commits": len(completed),
            "Auxiliary metadata-table commits": sum("/.hoodie/metadata/.hoodie/timeline/" in path and path.endswith((".commit", ".deltacommit", ".replacecommit")) for path in metadata.get("auxiliary_timeline_files", metadata.get("timeline_files", []))),
            "Latest completed instant": PurePosixPath(completed[-1]).name if completed else "Not captured",
            "Latest operation": record.get("operationType", "Not captured"),
            "Business-table log objects": sum(".log." in obj["path"] and "/.hoodie/metadata/" not in obj["path"] for obj in item["inventory"]),
            "Auxiliary metadata-table log objects": sum(".log." in obj["path"] and "/.hoodie/metadata/" in obj["path"] for obj in item["inventory"]),
            "Captured business Parquet objects": sum(obj["path"].endswith(".parquet") and "/.hoodie/metadata/" not in obj["path"] for obj in item["inventory"])}
