"""Open the actual local Jupyter notebook UI without executing duplicate lab writes."""
import json
import subprocess
from pathlib import Path
from urllib.parse import quote
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compose_lab import LOCAL_LAB, compose_command

from playwright.sync_api import sync_playwright


def main():
    command = compose_command("exec", "-T", "notebook", "jupyter", "server", "list", "--json")
    result = subprocess.run(command,check=True,capture_output=True,text=True)
    servers = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    if not servers:
        raise RuntimeError("No running local Jupyter server")
    url = "http://127.0.0.1:8888/lab/tree/notebooks/Olist_Table_Formats.ipynb"
    token = servers[0].get("token", "")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":1440,"height":1000})
        page.goto(url+"?token="+quote(token),wait_until="domcontentloaded")
        page.wait_for_selector(".jp-Notebook",timeout=60000)
        assert page.locator(".jp-Notebook .jp-Cell").count() > 0
        assert "Olist_Table_Formats.ipynb" in page.locator("body").inner_text()
        notebook=page.locator(".jp-Notebook:visible").first
        assert "Olist metadata" in notebook.inner_text()
        notebook.click(position={"x":120,"y":100})
        assert notebook.locator(".jp-Cell.jp-mod-active").count() > 0
        current=json.loads((LOCAL_LAB / "evidence/olist/current.json").read_text())["run_id"]
        output=(LOCAL_LAB / "evidence/olist/checks")/current
        output.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(output/"notebook-ui.png"))
        browser.close()
    report={"status":"PASS","url":url,"checks":["authenticated local JupyterLab opens","guided notebook renders","notebook cell selection responds"],
            "note":"No duplicate lab stages executed by this UI check; top-to-bottom execution is recorded separately"}
    (output/"notebook-ui-verification.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
