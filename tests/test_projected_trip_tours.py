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
            "origin": [1, 1, 2],
            "destination": [8, 9, 10],
            "tour_mode": ["WALK", "BIKE", "WALK"],
        },
        index=[10, 20, 30],
    )
    persons = pd.DataFrame(
        {
            "tour_mode": ["unused", "unused"],
            "age": [20, 30],
            "income": [10.0, 20.0],
            "unused": [100, 200],
        },
        index=[3, 4],
    )
    tables = {
        "laptop_memory.yaml": {"project_trip_tours": laptop},
        "trip_mode_choice.yaml": {
            "TOURS_MERGED_CHOOSER_COLUMNS": ["person_id", "tour_mode", "age"]
        },
        "trip_destination.yaml": {"LOGSUM_SETTINGS": "test_logsum.yaml"},
        "test_logsum.yaml": {"TOURS_MERGED_CHOOSER_COLUMNS": ["income", "age"]},
    }
    state = SimpleNamespace(
        _context={},
        current_model_name=model,
        filesystem=SimpleNamespace(read_model_settings=tables.__getitem__),
    )
    tour_before, person_before = tours.copy(), persons.copy()
    actual = projected.tours_merged(state, tours, persons)
    expected = projected.simple_table_join(tours, persons, "person_id")
    if laptop and model in projected.TRIP_MODELS:
        expected = expected.drop(columns="unused")
    pd.testing.assert_frame_equal(actual, expected)
    pd.testing.assert_frame_equal(tours, tour_before)
    pd.testing.assert_frame_equal(persons, person_before)
