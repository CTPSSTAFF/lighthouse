"""Check committed inputs without loading the large skim arrays."""

import json
from pathlib import Path

import openmatrix as omx
import pandas as pd
import yaml

ROOT = Path(__file__).parents[1]
DATA = ROOT / "model/data"
CONFIGS = ROOT / "model/configs"


def test_input_schema_matches_configuration():
    settings = yaml.safe_load((CONFIGS / "settings.yaml").read_text())
    for table in settings["input_table_list"]:
        header = pd.read_csv(DATA / table["filename"], nrows=0)
        renamed = header.rename(columns=table.get("rename_columns", {}))
        required = set(table["keep_columns"]) | {table["index_col"]}
        assert required.issubset(renamed.columns), (
            table["tablename"],
            required - set(renamed.columns),
        )


def test_frozen_households_exist_and_are_unique():
    ids = json.loads((ROOT / "tests/fixtures/household_ids.json").read_text())[
        "household_ids"
    ]
    households = pd.read_csv(DATA / "households.csv", usecols=["household_id"])
    assert len(ids) == len(set(ids)) == 10000
    assert set(ids).issubset(set(households.household_id))


def test_skim_dimensions_and_zone_mapping():
    zones = pd.read_csv(DATA / "land_use.csv", usecols=["TAZ"]).TAZ
    assert zones.is_unique and zones.notna().all()
    los = yaml.safe_load((CONFIGS / "network_los.yaml").read_text())
    names = []
    for pattern in los["taz_skims"]:
        paths = sorted(DATA.glob(pattern))
        assert paths, f"No skims match {pattern}"
        for path in paths:
            with omx.open_file(str(path), "r") as skims:
                assert skims.shape() == (len(zones), len(zones)), path
                mappings = skims.list_mappings()
                assert mappings, f"No zone mapping in {path}"
                for mapping in mappings:
                    zone_map = skims.mapping(mapping)
                    assert set(zone_map) == set(zones), (path, mapping)
                    assert set(zone_map.values()) == set(range(len(zones))), (
                        path,
                        mapping,
                    )
                for name in skims.list_matrices():
                    assert skims[name].shape == (len(zones), len(zones)), (path, name)
                    names.append(name)
    assert len(names) == len(set(names)), "Duplicate matrix names across skim files"
