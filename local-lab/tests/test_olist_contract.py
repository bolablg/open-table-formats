"""Contract tests use tiny synthetic fixtures, never saved lab results."""
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from olist_contract import COLUMNS, article_config, expected_rows, json_rows, row_diff, source_selection


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "orders.csv"
        self.rows = [{"order_id": f"{index:032x}", "customer_id": f"{index+1000:032x}",
                     "order_status": "delivered", "order_purchase_timestamp": "2017-01-01 12:30:00",
                     "order_approved_at": "2017-01-01 13:00:00", "order_delivered_carrier_date": None,
                     "order_delivered_customer_date": None, "order_estimated_delivery_date": "2017-01-15 00:00:00"}
                    for index in range(120)]
        self.write(self.rows)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rows):
        with self.path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def test_selection_is_order_independent_and_source_is_untouched(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        sample, manifest = source_selection(self.path)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)
        self.assertEqual(manifest["sha256"], before)
        self.write(list(reversed(self.rows)))
        reordered, _ = source_selection(self.path)
        self.assertEqual(sample, reordered)
        self.assertEqual(len({r["order_id"] for r in sample}), 5)
        self.assertFalse({r["order_id"] for r in sample[:3]} & {r["order_id"] for r in sample[3:]})
        self.assertEqual(manifest["preset_id"], "article")
        self.assertEqual(manifest["stage_order"], ["create", "insert", "delete"])
        self.assertEqual(manifest["delete_sample_ranks"], [2])

    def test_mutations_change_only_the_promised_rows_and_fields(self):
        sample, _ = source_selection(self.path)
        states = [json_rows(expected_rows(sample, stage)) for stage in article_config()["stages"]]
        self.assertEqual([len(rows) for rows in states], [3, 5, 4])
        inserted = row_diff(states[0], states[1])
        self.assertEqual(len(inserted["inserted"]), 2)
        self.assertEqual(inserted["updated"], [])
        deleted = row_diff(states[1], states[2])
        self.assertEqual(len(deleted["deleted"]), 1)
        self.assertEqual(deleted["deleted"][0]["order_id"], sample[1]["order_id"])
        self.assertEqual(deleted["updated"], [])
        self.assertEqual(deleted["inserted"], [])
        self.assertTrue(all(r["order_delivered_customer_date"] is None for r in states[2]))

    def test_custom_counts_seed_and_reproducibility(self):
        config=article_config(4,3,2,"reader-example-v1")
        sample, manifest=source_selection(self.path,config)
        self.assertEqual(len(sample),7)
        self.assertEqual(manifest["expected_rows"],[4,7,5])
        states=[json_rows(expected_rows(sample,stage,config)) for stage in config["stages"]]
        self.assertEqual([len(state) for state in states],[4,7,5])
        self.assertEqual(len(row_diff(states[0],states[1])["inserted"]),3)
        self.assertEqual(len(row_diff(states[1],states[2])["deleted"]),2)
        self.write(list(reversed(self.rows)))
        repeat, reordered=source_selection(self.path,config)
        self.assertEqual(sample,repeat)
        self.assertEqual(manifest["sample_sha256"],reordered["sample_sha256"])
        other,_=source_selection(self.path,article_config(4,3,2,"another-seed"))
        self.assertNotEqual(sample,other)

    def test_invalid_counts_seed_and_source_capacity(self):
        invalid=[{"initial_rows":0},{"initial_rows":-1},{"insert_rows":-1},{"delete_rows":-1},
                 {"delete_rows":6},{"initial_rows":True},{"insert_rows":1.5},
                 {"sample_seed":""},{"sample_seed":"  "},{"sample_seed":3}]
        for settings in invalid:
            with self.subTest(settings=settings),self.assertRaises(ValueError):
                article_config(**settings)
        self.write(self.rows[:4])
        with self.assertRaisesRegex(ValueError, "At least 5"):
            source_selection(self.path)

    def test_zero_changes_and_delete_every_row(self):
        zero=article_config(2,0,0)
        sample,_=source_selection(self.path,zero)
        states=[json_rows(expected_rows(sample,stage,zero)) for stage in zero["stages"]]
        self.assertEqual(states[0],states[1])
        self.assertEqual(states[1],states[2])
        all_rows=article_config(2,1,3)
        sample,_=source_selection(self.path,all_rows)
        self.assertEqual(expected_rows(sample,"delete",all_rows),[])
        self.assertEqual(len(set(all_rows["delete_indices"])),3)

    def test_rejects_duplicate_keys_and_invalid_timestamps(self):
        self.write(self.rows + [self.rows[0]])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            source_selection(self.path)
        self.rows[0]["order_approved_at"] = "invalid"
        self.write(self.rows)
        with self.assertRaises(ValueError):
            source_selection(self.path)

    def test_rejects_missing_required_value(self):
        self.rows[0]["order_estimated_delivery_date"] = None
        self.write(self.rows)
        with self.assertRaisesRegex(ValueError, "required"):
            source_selection(self.path)


if __name__ == "__main__":
    unittest.main()
