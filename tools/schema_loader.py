import json
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent


def load_schema_catalog():
    path = (
        BASE_DIR
        / "semantic_layer"
        / "schema_catalog.json"
    )

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_metric_definitions():
    path = (
        BASE_DIR
        / "semantic_layer"
        / "metric_definitions.yaml"
    )

    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_business_glossary():
    path = (
        BASE_DIR
        / "semantic_layer"
        / "business_glossary.yaml"
    )

    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)