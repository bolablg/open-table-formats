"""Browser interactions against real generated evidence, not fixture results."""
import argparse
import json
from pathlib import Path
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "evidence/olist")
    args = parser.parse_args()
    with urllib.request.urlopen(args.url + "/api/status") as response:
        status = json.load(response)
    run = next(run for run in status["runs"] if run["run_id"] == status["current_run_id"])
    if run["status"] != "completed":
        raise RuntimeError("UI verification requires a newly completed Olist run")
    assert run["preset_id"] == "article" and run["completed_stages"] == ["create", "insert", "delete"]
    config=run["configuration"]
    initial,inserted,deleted=config["initial_rows"],config["insert_rows"],config["delete_rows"]
    counts=config["counts"]
    saved = json.loads((args.output_dir / "runs" / run["run_id"] / "delete.json").read_text())
    args.output_dir = args.output_dir / "checks" / run["run_id"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    iceberg = next(item for item in saved["formats"] if item["format"] == "iceberg")
    documents = [json.loads(file["text"]) for file in iceberg["raw_metadata"]["files"]
                 if file["path"].endswith(".metadata.json") and "text" in file]
    exact_snapshot_id = str(max(documents, key=lambda doc: doc["last-updated-ms"])["current-snapshot-id"])
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":1440,"height":1080})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_selector(".card")
        assert page.locator(".card").count() == 3
        assert page.locator("#stage").input_value() == "delete"
        assert page.locator(".card .number").first.inner_text().startswith(str(counts[-1]))
        assert page.locator("#stage option").count() == 3
        assert " → ".join(map(str,counts)) in page.locator("#provenance").inner_text()
        assert config["sample_seed"] in page.locator(".intro").inner_text()
        assert all("olist_article_" in value for value in page.locator("#run option").evaluate_all("nodes=>nodes.map(node=>node.value)"))
        checks.append("current run and latest completed stage load")
        for stage,count,change in [("create",counts[0],f"Initial rows · {initial}"),("insert",counts[1],f"Inserted · {inserted}"),("delete",counts[2],f"Deleted · {deleted}")]:
            page.select_option("#stage",stage)
            page.wait_for_function("count => document.querySelector('.card .number')?.textContent.trim().startsWith(String(count))",arg=count)
            page.locator('[data-view="changes"]').click()
            page.wait_for_selector(".change-heading")
            assert change in page.locator("#content").inner_text()
            checks.append(stage + " rows and business changes")
        for name in ["iceberg","delta","hudi"]:
            page.select_option("#format",name)
            page.locator('[data-view="schema"]').click()
            assert page.locator(".panel").count() == 1
            assert "order_id" in page.locator("#content").inner_text()
            assert "sales_channel" not in page.locator("#content").inner_text()
        checks.append("all format selections and native eight-column schema")
        page.locator('[data-view="rows"]').click()
        page.fill("#search","__no_matching_value__")
        assert f"0 of {counts[-1]}" in page.locator("#content").inner_text()
        page.fill("#search","")
        checks.append("row filtering and null-safe rendering")
        page.locator('[data-view="metadata"]').click()
        summary = page.locator(".panel table").first
        assert "Business-table log objects" in summary.inner_text()
        assert "Auxiliary metadata-table log objects" in summary.inner_text()
        business_logs = summary.locator("tr").filter(has_text="Business-table log objects")
        assert business_logs.locator("td").nth(1).inner_text() == "0"
        assert 'lab.spark.read.format("hudi").load(' in page.locator(".path").inner_text()
        assert not page.locator("#search-label").is_visible()
        checks.append("Hudi business and auxiliary metadata counts stay separate")
        page.locator(".panel details").first.locator("summary").click()
        assert "timeline_files" in page.locator("#content").inner_text()
        assert page.locator(".panel details").count() > 1
        checks.append("actual metadata and raw inspection expand")
        page.locator('[data-view="files"]').click()
        assert "Object presence, size and modification time" in page.locator("#content").inner_text()
        checks.append("changed-file inventory")
        page.select_option("#format","all")
        assert page.locator(".panel").count() == 3
        page.locator("#refresh").click()
        page.wait_for_selector(".card")
        assert page.locator("#stage").input_value() == "delete"
        checks.append("comparison and evidence refresh")
        with page.expect_download() as download:
            page.locator("#download").click()
        downloaded = args.output_dir / "ui-downloaded-evidence.json"
        download.value.save_as(downloaded)
        payload = json.loads(downloaded.read_text())
        assert payload["run_id"] == run["run_id"] and payload["stage"] == "delete" and payload["preset_id"] == "article"
        assert len(payload["formats"]) == 3
        checks.append("download contains the selected actual snapshot")
        downloaded_iceberg = next(item for item in payload["formats"] if item["format"] == "iceberg")
        assert downloaded_iceberg["metadata_summary"]["Current snapshot ID"] == exact_snapshot_id
        page.locator('[data-view="metadata"]').click()
        snapshot_row = page.locator('.panel[data-format="iceberg"] table').first.locator("tr").filter(has_text="Current snapshot ID")
        assert snapshot_row.locator("td").nth(1).inner_text() == exact_snapshot_id
        checks.append("large snapshot ID matches raw capture exactly in UI and download")
        page.screenshot(path=str(args.output_dir / "ui-desktop.png"),full_page=True)
        page.set_viewport_size({"width":390,"height":844})
        page.locator('[data-view="rows"]').click()
        page.screenshot(path=str(args.output_dir / "ui-mobile.png"),full_page=True)
        assert page.locator("#refresh").is_visible()
        checks.append("mobile viewport renders controls")
        custom = next((candidate for candidate in status["runs"] if candidate.get("configuration",{}).get("counts")==[4,7,5] and candidate["status"]=="completed"), None)
        if custom:
            page.select_option("#run",custom["run_id"])
            page.wait_for_function("() => document.querySelector('.intro h1')?.textContent.includes('4 → 7 → 5')")
            page.wait_for_function("() => document.querySelector('.card .number')?.textContent.trim().startsWith('5')")
            assert custom["configuration"]["sample_seed"] in page.locator(".intro").inner_text()
            assert [option for option in page.locator("#stage option").all_text_contents() if "rows" in option]
            checks.append("custom run selection displays its counts and seed")
        empty_run = next((candidate for candidate in status["runs"] if candidate.get("configuration",{}).get("counts")==[2,3,0] and candidate["status"]=="completed"), None)
        if empty_run:
            page.select_option("#run",empty_run["run_id"])
            page.wait_for_function("() => document.querySelector('.card .number')?.textContent.trim().startsWith('0')")
            assert "No rows in this selection" in page.locator("#content").inner_text()
            checks.append("delete-all run displays a valid empty table")
        zero_run = next((candidate for candidate in status["runs"] if candidate.get("configuration",{}).get("counts")==[2,2,2] and candidate["status"]=="completed"), None)
        if zero_run:
            page.select_option("#run",zero_run["run_id"])
            page.wait_for_function("() => document.querySelector('#question')?.textContent.includes('no-op')")
            assert page.locator(".card .number").first.inner_text().startswith("2")
            checks.append("zero-change run displays the no-op label")
        page.goto(args.url + "/legacy",wait_until="networkidle")
        page.wait_for_selector(".card")
        assert page.locator(".intro h1").inner_text() == "Earlier runs"
        assert "Earlier run" in page.locator("#notice").inner_text()
        assert not page.locator("#run").input_value().startswith("olist_article_")
        checks.append("earlier runs are separate from the configurable Olist walkthrough")
        assert not errors, "Browser JavaScript errors: " + str(errors)
        browser.close()
    report = {"status":"PASS","run_id":run["run_id"],"checks":checks,"browser_errors":errors}
    (args.output_dir / "ui-verification.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
