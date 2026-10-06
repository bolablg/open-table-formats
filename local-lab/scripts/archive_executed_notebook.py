"""Retain each completed tiny notebook in its own run directory."""
import json
from pathlib import Path
import shutil

project = Path(__file__).resolve().parent.parent
output = project / "evidence/olist"
run_id = json.loads((output / "current.json").read_text())["run_id"]
manifest = json.loads((output / "runs" / run_id / "manifest.json").read_text())
notebook = output / "executed-tiny-walkthrough.ipynb"
assert manifest["preset_id"] == "article" and manifest["status"] == "completed"
assert run_id in notebook.read_text()
target = output / "runs" / run_id / "executed-notebook.ipynb"
if target.exists():
    raise ValueError("This run already has an executed notebook; refusing to overwrite it")
shutil.copy2(notebook, target)
print("Executed notebook retained: " + str(target))
