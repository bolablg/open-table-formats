"""Static independence contract for the source manual notebook; no Spark needed."""

import ast
import json
from pathlib import Path
import unittest


NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks/Olist_Table_Formats_Manual.ipynb"


class ManualNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK.read_text())
        cls.code = ["".join(cell["source"]) for cell in cls.notebook["cells"] if cell["cell_type"] == "code"]
        cls.source = "\n".join(cls.code)
        cls.trees = [ast.parse(source) for source in cls.code]

    def test_only_standard_library_and_pyspark_imports(self):
        allowed = {"csv", "hashlib", "heapq", "json", "os", "re", "uuid", "datetime", "pathlib", "urllib", "pyspark"}
        for tree in self.trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(alias.name.split(".")[0] in allowed for alias in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module.split(".")[0], allowed)

    def test_no_helpers_or_external_script_execution(self):
        for tree in self.trees:
            self.assertFalse(any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in ast.walk(tree)))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"exec", "eval", "compile", "__import__"})
        for fragment in ("%run", "!python", "sys.path", "subprocess", "runpy", "/workspace/scripts", "lab_common", "olist_adapters"):
            self.assertNotIn(fragment, self.source)

    def test_one_explicit_spark_session(self):
        self.assertEqual(self.source.count("SparkSession.builder"), 1)
        self.assertEqual(self.source.count("builder.getOrCreate()"), 1)
        self.assertEqual(self.source.count("spark.stop()"), 1)

    def test_no_explorer_s3_or_evidence_dependency(self):
        for fragment in ("s3a://", "S3_ENDPOINT", "LocalStack", "current.json", "EVIDENCE", "write_text", "write_bytes"):
            self.assertNotIn(fragment, self.source)
        self.assertIn('Path("manual-output")', self.source)

    def test_twelve_visible_business_value_checks(self):
        for expected in ("expected_create", "expected_insert", "expected_update", "expected_delete"):
            for rows in ("iceberg_rows", "delta_rows", "hudi_rows"):
                self.assertIn(f"assert {rows} == {expected}", self.source)
        self.assertIn("SOURCE_SHA256", self.source)
        for dangerous in ("DROP TABLE", "shutil.rmtree", '.mode("overwrite")'):
            self.assertNotIn(dangerous, self.source)

    def test_source_is_output_free(self):
        for cell in self.notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
        self.assertNotIn("\u2014", NOTEBOOK.read_text())


if __name__ == "__main__":
    unittest.main()
