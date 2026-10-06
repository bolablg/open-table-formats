"""Exercise custom/edge configurations on the real local three-format stack."""
import json
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from olist_lab import OlistLab, atomic_json, utc_now


def main():
    owner=OlistLab.resume()
    checks=[]
    try:
        invalid_before=set((owner.output/"runs").iterdir())
        for settings in [dict(delete_rows=6),dict(initial_rows=owner.manifest["source"]["row_count"]+1)]:
            try:
                OlistLab.start(spark=owner.spark,**settings)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid configuration was accepted")
        assert set((owner.output/"runs").iterdir())==invalid_before
        for index,settings in enumerate([dict(initial_rows=4,insert_rows=3,delete_rows=2,sample_seed="reader-example-v1"),
                         dict(initial_rows=2,insert_rows=0,delete_rows=0,sample_seed="zero-change-v1"),
                         dict(initial_rows=2,insert_rows=1,delete_rows=3,sample_seed="delete-all-v1")]):
            if index==0:
                command=[sys.executable,str(Path(__file__).resolve().parents[1]/"scripts/olist_stage.py"),"new"]
                for name,value in settings.items():
                    command.extend(["--"+name.replace("_","-"),str(value)])
                initialized=subprocess.run(command,check=True,capture_output=True,text=True)
                created=json.loads(initialized.stdout)
                lab=OlistLab(created["run_id"],spark=owner.spark)
                assert all(lab.config[name]==value for name,value in settings.items())
            else:
                lab=OlistLab.start(spark=owner.spark,**settings)
            stages=[]
            for stage in lab.stages:
                result=lab.stage(stage)
                if result["write_action"]=="no-op":
                    assert all(not item["file_changes"][kind] for item in result["formats"] for kind in ["added","removed","changed"])
                assert all(item["validation"]["status"]=="PASS" for item in result["formats"])
                stages.append({"stage":stage,"rows":result["expected_rows"],"write_action":result["write_action"],
                               "formats":[item["format"] for item in result["formats"]]})
            checks.append({"run_id":lab.run_id,"configuration":settings,"status":"PASS","stages":stages,
                           "initialization":"CLI parameters" if index==0 else "Python API"})
        report={"status":"PASS","default_run_id":owner.run_id,"checked_at":utc_now(),"configurations":checks,
                "invalid_configurations":"Rejected before run-directory/table creation; count bounds and source capacity"}
        atomic_json(owner.output/"checks"/owner.run_id/"configuration-verification.json",report)
        print(json.dumps(report,indent=2))
    finally:
        # Restore the default run selection without changing saved results.
        atomic_json(owner.output/"current.json",{"run_id":owner.run_id})
        owner.spark.stop()


if __name__=="__main__":
    main()
