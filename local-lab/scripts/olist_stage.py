"""Run one named Olist stage; the notebook imports the same OlistLab API."""
import argparse
import json

from olist_lab import OlistLab
from olist_contract import CORE_STAGES, SEED


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["new", *CORE_STAGES, "reset"])
    parser.add_argument("--initial-rows", type=int)
    parser.add_argument("--insert-rows", type=int)
    parser.add_argument("--delete-rows", type=int)
    parser.add_argument("--sample-seed")
    parser.add_argument("--run-id")
    parser.add_argument("--confirm-run-id")
    args = parser.parse_args()
    supplied = {name: getattr(args, name) for name in ["initial_rows", "insert_rows", "delete_rows", "sample_seed"] if getattr(args, name) is not None}
    if args.stage != "new" and supplied:
        parser.error("Configuration parameters belong to new; later stages use the saved manifest")
    lab = OlistLab.start(**supplied) if args.stage == "new" else OlistLab.resume(args.run_id)
    try:
        if args.stage == "reset":
            lab.reset(args.confirm_run_id)
            print(json.dumps({"run_id": lab.run_id, "status": "reset", "evidence_retained": True}))
        elif args.stage == "new":
            print(json.dumps({"run_id": lab.run_id, "configuration": lab.config, "source": lab.manifest["source"], "next_stage": "create"}, indent=2))
        else:
            result = lab.stage(args.stage)
            print(json.dumps({"run_id": lab.run_id, "stage": args.stage, "captured_at": result["captured_at"],
                "formats": [{"format": item["format"], "validation": item["validation"],
                             "files_added": len(item["file_changes"]["added"])} for item in result["formats"]]}, indent=2))
    finally:
        lab.spark.stop()


if __name__ == "__main__":
    main()
