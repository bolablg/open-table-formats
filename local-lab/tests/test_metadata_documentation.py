"""Synthetic tests for the read-only metadata documentation checker."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_metadata_documentation.py"
SPEC = importlib.util.spec_from_file_location("metadata_documentation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MetadataDocumentationTests(unittest.TestCase):
    def test_json_and_json_lines(self):
        self.assertEqual(MODULE.decode_text('{"id": 1}'), {"id": 1})
        self.assertEqual(
            MODULE.decode_text('{"add": {}}\n{"remove": {}}'),
            [{"add": {}}, {"remove": {}}],
        )

    def test_properties_keep_literal_dots_and_values_with_equals(self):
        self.assertEqual(
            MODULE.decode_text("#comment\nhoodie.table.type=COPY_ON_WRITE\noption=a=b\n"),
            {"hoodie.table.type": "COPY_ON_WRITE", "option": "a=b"},
        )

    def test_empty_markers_and_invalid_text(self):
        for text in ("", "3", "not structured", "{invalid"):
            self.assertIsNone(MODULE.decode_text(text))

    def test_embedded_statistics_and_schemas_are_included(self):
        names = MODULE.property_names({
            "stats": '{"numRecords": 1, "minValues": {"driver_id": "x"}}',
            "schemaString": '{"fields": [{"name": "driver_id", "nullable": true}]}',
        })
        self.assertTrue({"stats", "numRecords", "minValues", "fields", "name", "nullable"} <= names)
        self.assertNotIn("driver_id", names)

    def test_dynamic_map_keys_are_not_property_names(self):
        names = MODULE.property_names({
            "refs": {"experiment_branch": {"snapshot-id": 1, "type": "branch"}},
            "partitionToWriteStats": {"region=example": [{"numWrites": 1}]},
        })
        self.assertTrue({"refs", "snapshot-id", "type", "partitionToWriteStats", "numWrites"} <= names)
        self.assertNotIn("experiment_branch", names)
        self.assertNotIn("region=example", names)

    def test_only_field_column_entries_count(self):
        markdown = "Mention `missing` in prose.\n| Field | Meaning |\n| --- | --- |\n| `defined` | Explains `incidental`. |"
        self.assertEqual(MODULE.defined_names(markdown), {"defined"})

    def test_null_and_zero_fields_are_not_skipped(self):
        self.assertEqual(MODULE.property_names({"unused": None, "count": 0}), {"unused", "count"})

    def test_business_strings_are_not_decoded(self):
        self.assertEqual(MODULE.property_names({"comment": '{"secret": 1}'}), {"comment"})


if __name__ == "__main__":
    unittest.main()
