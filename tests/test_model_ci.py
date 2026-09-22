"""Contract checks use small explicit data, including deliberately corrupt outputs."""

import copy
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    "model_ci", Path(__file__).parents[1] / "scripts/model_ci.py"
)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


@pytest.fixture
def population():
    h = pd.DataFrame({"hhsize": [1]}, index=pd.Index([10], name="household_id"))
    p = pd.DataFrame(
        {"household_id": [10], "age": [40], "pemploy": [1]},
        index=pd.Index([20], name="person_id"),
    )
    return {"households": h, "persons": p}


@pytest.fixture
def outputs(population):
    tables = copy.deepcopy(population)
    tables["tours"] = pd.DataFrame(
        {
            "person_id": [20],
            "household_id": [10],
            "origin": [1],
            "destination": [2],
            "tour_mode": ["WALK"],
            "start": [8],
            "end": [17],
        },
        index=[30],
    )
    tables["trips"] = pd.DataFrame(
        {
            "person_id": [20, 20],
            "household_id": [10, 10],
            "tour_id": [30, 30],
            "origin": [1, 2],
            "destination": [2, 1],
            "trip_mode": ["WALK", "WALK"],
            "depart": [8, 17],
            "outbound": [True, False],
            "trip_num": [1, 1],
            "trip_count": [1, 1],
        },
        index=[40, 41],
    )
    return tables


def test_valid_outputs(population, outputs):
    ci.validate_outputs(population, outputs, [1, 2])


@pytest.mark.parametrize(
    "table,column,value,message",
    [
        ("persons", "household_id", 999, "unknown household"),
        ("households", "hhsize", 2, "hhsize"),
        ("tours", "person_id", 999, "unknown person"),
        ("trips", "tour_id", 999, "unknown tour"),
        ("trips", "destination", 999, "invalid destination"),
        ("tours", "start", 23, "invalid times"),
        ("trips", "depart", 25, "invalid departure"),
        ("trips", "trip_num", 2, "broken sequence"),
        ("trips", "trip_count", 2, "incorrect trip_count"),
        ("trips", "trip_mode", None, "missing mode"),
    ],
)
def test_rejects_corrupt_outputs(population, outputs, table, column, value, message):
    outputs[table].iloc[0, outputs[table].columns.get_loc(column)] = value
    with pytest.raises(ValueError, match=message):
        ci.validate_outputs(population, outputs, [1, 2])


def test_rejects_population_loss(population, outputs):
    population["households"].loc[99] = [1]
    with pytest.raises(ValueError, match="population changed"):
        ci.validate_outputs(population, outputs, [1, 2])


def test_rejects_duplicate_ids(population, outputs):
    outputs["trips"].index = [40, 40]
    with pytest.raises(ValueError, match="invalid IDs"):
        ci.validate_outputs(population, outputs, [1, 2])


def test_distribution_changes_are_advisory():
    report = ci.advisory(
        {"trips.trip_mode": {"WALK": 1.0}}, {"trips.trip_mode": {"CAR": 1.0}}
    )
    assert "+100.00 pp" in report
    assert "-100.00 pp" in report
