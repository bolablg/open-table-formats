"""Olist operations using the format readers and metadata inspectors."""
from pyspark.sql import functions as F

from format_adapters import IcebergAdapter, DeltaAdapter, HudiAdapter
from lab_common import list_objects


def sql_keys(keys):
    return ",".join("'" + key.replace("'", "''") + "'" for key in keys)


class OlistIceberg(IcebergAdapter):
    def __init__(self, spark, bucket, run_id):
        super().__init__(spark, bucket)
        catalog = "olist_" + run_id
        warehouse = f"s3a://{bucket}/olist/runs/{run_id}/iceberg"
        spark.conf.set(f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog")
        spark.conf.set(f"spark.sql.catalog.{catalog}.type", "hadoop")
        spark.conf.set(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        self.table = f"{catalog}.lab.orders"
        self.root = warehouse + "/lab/orders"

    def create(self, frame):
        frame.createOrReplaceTempView("olist_initial")
        namespace = self.table.rsplit(".", 1)[0]
        self.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {namespace}")
        self.spark.sql(f"""CREATE TABLE {self.table} USING iceberg
            TBLPROPERTIES ('format-version'='2', 'write.update.mode'='copy-on-write',
            'write.delete.mode'='copy-on-write') AS SELECT * FROM olist_initial""")

    def update_keys(self, keys):
        self.spark.sql(f"UPDATE {self.table} SET order_estimated_delivery_date = order_estimated_delivery_date + INTERVAL 1 DAY WHERE order_id IN ({sql_keys(keys)})")

    def delete_keys(self, keys):
        self.spark.sql(f"DELETE FROM {self.table} WHERE order_id IN ({sql_keys(keys)})")

    def evolve(self, frame):
        self.spark.sql(f"ALTER TABLE {self.table} ADD COLUMN sales_channel STRING")
        frame.select("order_id", "sales_channel").createOrReplaceTempView("olist_channels")
        self.spark.sql(f"MERGE INTO {self.table} t USING olist_channels s ON t.order_id=s.order_id WHEN MATCHED THEN UPDATE SET t.sales_channel=s.sales_channel")


class OlistDelta(DeltaAdapter):
    def __init__(self, spark, bucket, run_id):
        super().__init__(spark, bucket)
        self.root = f"s3a://{bucket}/olist/runs/{run_id}/delta/orders"
        self.identifier = f"delta.`{self.root}`"

    def update_keys(self, keys):
        self.spark.sql(f"UPDATE {self.identifier} SET order_estimated_delivery_date = order_estimated_delivery_date + INTERVAL 1 DAY WHERE order_id IN ({sql_keys(keys)})")

    def delete_keys(self, keys):
        self.spark.sql(f"DELETE FROM {self.identifier} WHERE order_id IN ({sql_keys(keys)})")

    def evolve(self, frame):
        self.spark.sql(f"ALTER TABLE {self.identifier} ADD COLUMNS (sales_channel STRING)")
        frame.select("order_id", "sales_channel").createOrReplaceTempView("olist_channels")
        self.spark.sql(f"MERGE INTO {self.identifier} t USING olist_channels s ON t.order_id=s.order_id WHEN MATCHED THEN UPDATE SET t.sales_channel=s.sales_channel")


class OlistHudi(HudiAdapter):
    def __init__(self, spark, bucket, run_id):
        super().__init__(spark, bucket)
        self.root = f"s3a://{bucket}/olist/runs/{run_id}/hudi/orders"
        self.base_options.pop("hoodie.datasource.write.precombine.field")
        self.base_options.update({
            "hoodie.table.name": "olist_orders",
            "hoodie.datasource.write.partitionpath.field": "",
            "hoodie.datasource.write.keygenerator.class": "org.apache.hudi.keygen.NonpartitionedKeyGenerator",
            "hoodie.record.merge.mode": "COMMIT_TIME_ORDERING",
        })

    def inspect(self):
        metadata = super().inspect()
        inventory = list_objects(self.spark, self.root)
        auxiliary_prefix = self.root + "/.hoodie/metadata/"
        main = [item for item in inventory if not item["path"].startswith(auxiliary_prefix)]
        auxiliary = [item for item in inventory if item["path"].startswith(auxiliary_prefix)]
        metadata["auxiliary_timeline_files"] = [path for path in metadata["timeline_files"] if path.startswith(auxiliary_prefix)]
        metadata["timeline_files"] = [path for path in metadata["timeline_files"] if not path.startswith(auxiliary_prefix)]
        metadata["parquet_file_count"] = sum(item["path"].endswith(".parquet") for item in main)
        metadata["merge_on_read_log_file_count"] = sum(".log." in item["path"] for item in main)
        metadata["auxiliary_metadata_table"] = {
            "parquet_objects": sum(item["path"].endswith(".parquet") for item in auxiliary),
            "log_objects": sum(".log." in item["path"] for item in auxiliary),
            "note": "Hudi's auxiliary metadata table has its own timeline and log objects; these do not make the business table Merge-on-Read",
        }
        metadata["merge_on_read_note"] = "The business table uses Copy-on-Write; auxiliary metadata-table logs are counted separately"
        return metadata


def olist_adapters(spark, bucket, run_id):
    return [OlistIceberg(spark, bucket, run_id), OlistDelta(spark, bucket, run_id), OlistHudi(spark, bucket, run_id)]
