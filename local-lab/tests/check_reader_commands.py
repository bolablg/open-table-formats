"""Verify displayed reader commands against the completed local tables."""
import json
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lab_common import jsonable
from olist_lab import OlistLab, atomic_json, utc_now


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    args=parser.parse_args()
    lab=OlistLab.resume(args.run_id)
    try:
        payload=json.loads((lab.run_dir/(lab.stages[-1]+".json")).read_text())
        checks=[]
        for item in payload["formats"]:
            if item.get("reader_language")=="python":
                assert item["format"]=="hudi"
                assert item["reader_command"]==f'lab.spark.read.format("hudi").load("{item["root"]}").show(truncate=False)'
                frame=lab.spark.read.format("hudi").load(item["root"])
            else:
                frame=lab.spark.sql(item["reader_command"])
            frame=frame.select(*item["validation"]["business_columns"])
            actual=jsonable([row.asDict(recursive=True) for row in frame.orderBy("order_id").collect()])
            assert actual==item["rows"], item["format"]+" reader differs from captured business values"
            checks.append({"format":item["format"],"status":"PASS","rows":len(actual)})
        report={"status":"PASS","run_id":lab.run_id,"checked_at":utc_now(),"checks":checks}
        atomic_json(lab.output/"checks"/lab.run_id/"reader-verification.json",report)
        print(json.dumps(report,indent=2))
    finally:
        lab.spark.stop()


if __name__=="__main__":
    main()
