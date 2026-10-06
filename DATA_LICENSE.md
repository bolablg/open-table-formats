# Olist data acquisition and license

Download the Brazilian E-Commerce Public Dataset by Olist directly from its [Kaggle dataset page](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Locate `olist_orders_dataset.csv` and set `OLIST_SOURCE_CSV` to its absolute path. Keep source data outside this repository. Authenticate to Kaggle yourself if required; this lab stores no download credentials.

The dataset page identifies CC BY-NC-SA 4.0. Review the current dataset license and [Creative Commons terms](https://creativecommons.org/licenses/by-nc-sa/4.0/) before using or distributing derived material. Retain attribution to Olist and the dataset source.

This repository includes no Olist CSV, selected source rows, executed notebooks, raw evidence or data logs. The source is mounted read-only. Runtime evidence contains source-derived records and must remain local. The optional synthetic generator creates an ignored CSV locally; no generated CSV is bundled.

The local notebook validates the complete source and selects `initial_rows + insert_rows` orders deterministically. Defaults use five selected orders and produce 3 → 5 → 4.
