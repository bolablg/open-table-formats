"""Check repository files for data, credentials and generated outputs."""
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE_NOTEBOOKS = {"local-lab/notebooks/Olist_Table_Formats.ipynb",
                    "local-lab/notebooks/Olist_Table_Formats_Manual.ipynb"}


def main():
    result = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    candidates = sorted(set(name.decode() for name in result.split(b"\0") if name))
    errors = []
    for name in candidates:
        path = ROOT / name
        lower = name.lower()
        if path.is_symlink():
            errors.append(f"Repository file is a symlink: {name}")
        if any(part in {"evidence", "backups", "__pycache__", ".ipynb_checkpoints", ".aws", "runtime"}
               for part in path.relative_to(ROOT).parts):
            errors.append(f"Runtime/archive candidate: {name}")
        if path.suffix.lower() in {".csv", ".parquet", ".avro", ".orc", ".log", ".pyc", ".pem", ".key"}:
            errors.append(f"Data/log/key candidate: {name}")
        if path.suffix == ".ipynb":
            if name not in SOURCE_NOTEBOOKS:
                errors.append(f"Unexpected notebook candidate: {name}")
            notebook = json.loads(path.read_text())
            if any(cell.get("outputs") or cell.get("execution_count") is not None
                   for cell in notebook["cells"] if cell["cell_type"] == "code"):
                errors.append(f"Notebook contains execution output: {name}")
            if set(notebook.get("metadata", {})) - {"kernelspec", "language_info"}:
                errors.append(f"Unexpected notebook metadata: {name}")
        if path.name.startswith(".env") and path.name != ".env.example":
            errors.append(f"Environment credential candidate: {name}")
        if path.is_file() and path.suffix not in {".ipynb", ".png"}:
            content = path.read_text(errors="replace")
            for expression in [r"AKIA[0-9A-Z]{16}", r"ASIA[0-9A-Z]{16}",
                               r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                               r"gh[pousr]_[A-Za-z0-9]{30,}"]:
                if re.search(expression, content):
                    errors.append(f"Credential-shaped content: {name}")
            if re.search(r"/(?:Volumes|Users)/[^\s\"']+", content):
                errors.append(f"Machine-specific path in repository file: {name}")
    probes = ["local-lab/evidence", "local-lab/evidence/olist/current.json",
              "local-lab/data/orders.csv", "local-lab/data/olist_orders_dataset.csv",
              "local-lab/notebooks/executed.ipynb", "local-lab/.env", "local-lab/.env.production",
              "local-lab/.aws/credentials", "local-lab/run.log", "local-lab/private.pem"]
    for name in probes:
        # Git cannot address descendants of a symlink. Check the ignored link itself.
        probe = Path(name)
        for parent in reversed(probe.parents):
            if (ROOT / parent).is_symlink():
                probe = parent
                break
        ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", "-q", str(probe)])
        if ignored.returncode != 0:
            errors.append(f"Expected exclusion missing: {name}")
    dockerignore = [line.strip() for line in (ROOT / "local-lab/.dockerignore").read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
    if dockerignore != ["*", "!Dockerfile.spark", "!Dockerfile.olist"]:
        errors.append("Docker context is not limited to the two Dockerfiles")
    for notebook in SOURCE_NOTEBOOKS:
        if notebook not in candidates:
            errors.append("Source notebook is missing: " + notebook)
    report = {"status": "FAIL" if errors else "PASS", "candidate_files": len(candidates),
              "exclusion_probes": len(probes), "source_notebooks": sorted(SOURCE_NOTEBOOKS),
              "docker_context": ["Dockerfile.spark", "Dockerfile.olist"], "errors": errors,
              "note": "Checks repository files, notebook outputs, data exclusions and credential patterns"}
    print(json.dumps(report, indent=2))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
