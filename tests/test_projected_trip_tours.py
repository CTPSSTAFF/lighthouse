"""Trip projections retain required attributes without changing tour rows or inputs."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "model"))
from extensions import projected_trip_tours as projected  # noqa: E402


@pytest.mark.parametrize(
    "model,laptop",
    [
        ("trip_destination", True),
        ("trip_purpose_and_destination", True),
        ("trip_mode_choice", True),
        ("atwork_subtour_destination", True),
        ("trip_destination", False),
    ],
)
def test_chooser_projection(model, laptop):
    tours = pd.DataFrame(
        {
            "person_id": [3, 3, 4],
            "household_id": [1, 1, 2],
            "origin": [1, 1, 2],
            "destination": [8, 9, 10],
            "tour_mode": ["WALK", "BIKE", "WALK"],
        },
        index=[10, 20, 30],
    )
    persons = pd.DataFrame(
        {
            "household_id": [1, 2],
            "tour_mode": ["unused", "unused"],
            "age": [20, 30],
            "income": [10.0, 20.0],
            "unused": [100, 200],
        },
        index=[3, 4],
    )
    households = pd.DataFrame(
        {"income": [100.0, 200.0], "hhsize": [2, 3]}, index=[1, 2]
    )
    tables = {
        "laptop_memory.yaml": {"project_trip_tours": laptop},
        "trip_mode_choice.yaml": {
            "TOURS_MERGED_CHOOSER_COLUMNS": ["person_id", "tour_mode", "age", "hhsize"]
        },
        "trip_destination.yaml": {"LOGSUM_SETTINGS": "test_logsum.yaml"},
        "test_logsum.yaml": {"TOURS_MERGED_CHOOSER_COLUMNS": ["income", "age"]},
    }
    full_persons = projected.simple_table_join(persons, households, "household_id")
    calls = []

    def dataframe(name, as_copy=False):
        calls.append(name)
        assert name == "persons_merged"
        return full_persons

    class State(SimpleNamespace):
        def __contains__(self, key):
            return key in self._context

        def drop(self, key):
            del self._context[key]

    state = State(
        _context={"persons_merged": full_persons},
        current_model_name=model,
        filesystem=SimpleNamespace(read_model_settings=tables.__getitem__),
        get_dataframe=dataframe,
    )
    before = [t.copy() for t in [tours, persons, households]]
    actual = projected.tours_merged(state, tours, persons, households)
    expected = projected.simple_table_join(tours, full_persons, "person_id")
    if laptop and model in projected.TRIP_MODELS:
        expected = expected[list(tours.columns) + ["age", "hhsize", "income"]]
        assert not calls  # no materialization of the wide provider table
        assert "persons_merged" not in state
    else:
        assert calls == ["persons_merged"]
    pd.testing.assert_frame_equal(actual, expected)
    for current, original in zip([tours, persons, households], before):
        pd.testing.assert_frame_equal(current, original)
