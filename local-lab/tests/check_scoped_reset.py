"""Docker integration checks using isolated metadata and disposable sentinels."""
import json
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from olist_lab import OlistLab, atomic_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    args=parser.parse_args()
    completed = OlistLab.resume(args.run_id)
    completed_id = completed.run_id
    try:
        try:
            completed.stage("update")
        except ValueError:
            pass
        else:
            raise AssertionError("Tiny run allowed an unsupported update stage")
        try:
            completed.stage("insert")
        except ValueError:
            pass
        else:
            raise AssertionError("Completed run allowed a repeated stage")
        os.environ["OLIST_EVIDENCE_DIR"] = "/workspace/evidence/olist/reset-check"
        lab = OlistLab.start(spark=completed.spark)
        prefix = f"s3a://{lab.bucket}/olist/runs/{lab.run_id}"
        jvm = lab.spark.sparkContext._jvm
        path = lambda value: jvm.org.apache.hadoop.fs.Path(value)
        fs = path(prefix).getFileSystem(lab.spark.sparkContext._jsc.hadoopConfiguration())
        owned = path(prefix + "/reset-sentinel.txt")
        protected = path(f"s3a://{lab.bucket}/olist/reset-check-protected/{lab.run_id}/sentinel.txt")
        for target in [owned, protected]:
            stream = fs.create(target, False)
            stream.writeUTF("Disposable reset check; no Olist business rows")
            stream.close()
        try:
            lab.reset("wrong-run")
        except ValueError:
            pass
        else:
            raise AssertionError("Reset accepted the wrong confirmation")
        assert fs.exists(owned) and fs.exists(protected)
        original_root = lab.adapters[0].root
        lab.adapters[0].root = f"s3a://{lab.bucket}/warehouse/iceberg/lab/orders"
        try:
            lab.reset(lab.run_id)
        except ValueError:
            pass
        else:
            raise AssertionError("Reset accepted an outside resource")
        lab.adapters[0].root = original_root
        assert fs.exists(owned) and fs.exists(protected)
        original_manifest=json.loads(lab.manifest_path.read_text())
        altered=json.loads(lab.manifest_path.read_text())
        altered["configuration"]["initial_rows"]+=1
        atomic_json(lab.manifest_path,altered)
        try:
            OlistLab(lab.run_id,spark=completed.spark)
        except ValueError as error:
            assert "sampling configuration changed" in str(error)
        else:
            raise AssertionError("Changed configuration was accepted on resume")
        finally:
            atomic_json(lab.manifest_path,original_manifest)
        # A separate test-only text file exercises the notebook's per-stage hash guard.
        probe = Path("/workspace/evidence/olist/reset-check/changed-source-probe.txt")
        probe.write_text("A test-only replacement, not the source CSV")
        original_source = lab.source_path
        lab.source_path = str(probe)
        try:
            lab.stage("create")
        except ValueError as error:
            assert "Source CSV changed" in str(error)
        else:
            raise AssertionError("Stage did not reject a changed source")
        lab.source_path = original_source
        assert not (lab.run_dir / "create.json").exists()
        lab.reset(lab.run_id)
        assert not fs.exists(owned) and fs.exists(protected)
        assert lab.manifest_path.exists()  # Evidence is retained and explicitly marked reset.
        fs.delete(protected.getParent(), True)
        probe.unlink()
        result = {"status":"PASS", "completed_run_id":completed_id, "reset_probe_run_id":lab.run_id,
                  "checks":["unsupported stage rejected", "completed-run stage replay rejected", "wrong reset confirmation rejected",
                            "outside prefix rejected before deletion", "changed sampling configuration rejected on resume", "changed source rejected before writes",
                            "only owned sentinel deleted", "outside sentinel preserved", "reset evidence retained"]}
        atomic_json(Path("/workspace/evidence/olist/checks")/completed_id/"reset-verification.json", result)
        print(json.dumps(result,indent=2))
    finally:
        completed.spark.stop()


if __name__ == "__main__":
    main()
