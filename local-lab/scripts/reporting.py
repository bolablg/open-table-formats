"""Write machine-readable and reader-friendly Lab 1 evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_reports(payload: dict[str, Any], output_dir: str) -> tuple[Path, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "lab1-report.json"
    markdown_path = target / "lab1-report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Lab 1 evidence: the same changes, three metadata systems",
        "",
        f"Status: **{payload['status']}**",
        "",
        "The assertions compare every business row after each operation. The object counts show that equal logical results do not imply equal metadata or file layouts.",
        "",
        "| Stage | Expected rows | Iceberg | Delta Lake | Hudi |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for stage in payload["stages"]:
        counts = {item["format"]: item["validation"]["row_count"] for item in stage["formats"]}
        lines.append(
            f"| {stage['stage']} | {stage['expected_row_count']} | {counts['iceberg']} | {counts['delta']} | {counts['hudi']} |"
        )

    lines.extend(["", "## Physical changes by operation", ""])
    for stage in payload["stages"]:
        lines.extend([f"### {stage['stage']}", ""])
        for item in stage["formats"]:
            delta = item["object_delta"]
            lines.append(
                f"- **{item['format']}**: {len(delta['added'])} objects added, "
                f"{len(delta['removed'])} removed, {len(delta['size_changed'])} changed size."
            )
        lines.append("")

    final_metadata = payload["stages"][-1]["formats"]
    lines.extend(["## What the final metadata says", ""])
    for item in final_metadata:
        metadata = item["metadata"]
        lines.append(f"- **{item['format']}**: {metadata['what_to_notice']}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "All three formats preserved the same table result through inserts, updates, deletes, and a schema change. Their metadata is not interchangeable: Iceberg organizes snapshots and manifests, Delta records ordered transaction-log actions, and Hudi records timeline instants plus file-group state. That metadata layer—not Parquet alone—is what makes the files behave like a table.",
            "",
            "The run is an educational correctness experiment, not a benchmark. It uses one Spark process, no concurrent writers, and Hudi Copy-on-Write.",
        ]
    )
    return "\n".join(lines) + "\n"
