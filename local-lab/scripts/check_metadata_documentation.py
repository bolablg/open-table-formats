"""Read-only checks that saved metadata property names have reference entries.

This checks documentation presence, not the correctness of a definition. It
needs local evidence, which is deliberately not bundled in the Git repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


MAP_KEYS_ARE_DATA = {
    "partitionToWriteStats", "readable_metrics", "minValues", "maxValues",
    "nullCount", "column_sizes", "value_counts", "null_value_counts",
    "nan_value_counts", "lower_bounds", "upper_bounds", "refs",
    "indexDefinitions", "total_action_counts", "actions",
}
REFERENCE_FILES = {
    "iceberg": "iceberg-field-reference.md",
    "delta": "delta-field-reference.md",
    "hudi": "hudi-field-reference.md",
}


def decode_text(text: str):
    """Decode captured JSON/JSONL or Java-style properties without writing."""
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            try:
                return [json.loads(line) for line in stripped.splitlines() if line.strip()]
            except json.JSONDecodeError:
                return None
    if "=" in stripped:
        return {
            line.split("=", 1)[0]: line.split("=", 1)[1]
            for line in stripped.splitlines()
            if line and not line.startswith(("#", "!")) and "=" in line
        }
    return None


def property_names(value, parent: str = "") -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if parent not in MAP_KEYS_ARE_DATA and not str(key).isdigit():
                names.add(str(key))
            names.update(property_names(child, str(key)))
    elif isinstance(value, list):
        for child in value:
            names.update(property_names(child, parent))
    elif isinstance(value, str):
        # Only decode known structured text fields. Do not mistake business
        # string values or arbitrary binary-bound renderings for properties.
        if parent in {"text", "schemaString", "stats", "schema", "latest_schema"}:
            decoded = decode_text(value)
            if decoded is not None:
                names.update(property_names(decoded))
    return names


def defined_names(markdown: str) -> set[str]:
    """Only table field cells count, not incidental mentions in prose."""
    names: set[str] = set()
    for line in markdown.splitlines():
        if line.startswith("| "):
            cell = line.split("|", 2)[1]
            names.update(re.findall(r"`([^`]+)`", cell))
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    lab = Path(__file__).resolve().parents[1]
    parser.add_argument("--evidence-root", type=Path, default=lab / "evidence/olist")
    parser.add_argument("--run-id", help="Defaults to the local current.json pointer")
    parser.add_argument("--docs", type=Path, default=lab.parent / "metadata-description")
    args = parser.parse_args()
    run_id = args.run_id
    if run_id is None:
        run_id = json.loads((args.evidence_root / "current.json").read_text())["run_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        parser.error("run ID must be a single safe directory name")
    observed = {name: set() for name in REFERENCE_FILES}
    for stage in ("create", "insert", "delete"):
        snapshot = json.loads((args.evidence_root / "runs" / run_id / f"{stage}.json").read_text())
        for item in snapshot["formats"]:
            names = observed[item["format"]]
            for section in ("metadata", "raw_metadata", "inventory", "file_changes"):
                names.update(property_names(item[section]))
    common = defined_names((args.docs / "capture-field-reference.md").read_text())
    failed = False
    for name, filename in REFERENCE_FILES.items():
        markdown = (args.docs / filename).read_text()
        missing = sorted(observed[name] - common - defined_names(markdown))
        if missing:
            failed = True
            print(f"FAIL {name}: missing property entries: {', '.join(missing)}")
        else:
            print(f"PASS {name}: {len(observed[name])} distinct captured property names have entries")
    for path in sorted(args.docs.glob("*.md")):
        markdown = path.read_text()
        if "\u2014" in markdown:
            failed = True
            print(f"FAIL {path.name}: em dash")
        for target in re.findall(r"\]\(([^)]+)\)", markdown):
            if "://" in target or target.startswith("#"):
                continue
            if not (path.parent / target.split("#", 1)[0]).exists():
                failed = True
                print(f"FAIL {path.name}: missing relative target {target}")
    print("Name coverage is not semantic validation or decoding of uncaptured files.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
