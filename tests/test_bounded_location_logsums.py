"""Keep duplicate chooser IDs and sample order through bounded logsum joins."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "model"))
from extensions import bounded_location_logsums as bounded  # noqa: E402


@pytest.mark.parametrize("rows", [0, 2, 3, 100])
def test_sample_order_and_values(monkeypatch, rows):
    seen = []
    draws = {}

    def evaluate(state, segment, persons, los, sample, *args):
        seen.append(len(sample))
        for chooser in sample.index.unique():
            draws[chooser] = draws.get(chooser, 0) + 1
        merged = sample.join(persons)
        sample[bounded.location_choice.ALT_LOGSUM] = (
            np.logaddexp(merged.destination.to_numpy(), merged.age.to_numpy())
            + sample.index.map(draws).to_numpy()
        )
        return sample

    monkeypatch.setattr(bounded, "_run_location_logsums", evaluate)
    state = SimpleNamespace(
        filesystem=SimpleNamespace(
            read_model_settings=lambda _: {"location_logsum_rows": rows}
        )
    )
    persons = pd.DataFrame({"age": [10.0, 20.0]}, index=[1, 2])
    sample = pd.DataFrame(
        {"destination": [2.0, 3.0, 4.0, 5.0, 6.0]}, index=[1, 1, 1, 2, 2]
    )
    expected = evaluate(state, "school", persons, None, sample.copy())
    seen.clear()
    draws.clear()
    actual = bounded.run_location_logsums(
        state, "school", persons, None, sample, None, 0, "school", "school"
    )
    assert draws == {1: 1, 2: 1}
    assert actual is sample
    pd.testing.assert_frame_equal(actual, expected)
    assert max(seen) <= (max(rows, 3) if rows else len(sample))


def test_tour_person_join(monkeypatch):
    seen = []

    def evaluate(state, purpose, persons, sample, *args):
        seen.append(len(sample))
        merged = sample.merge(
            persons, left_on="person_id", right_index=True, how="left"
        )
        sample[bounded.location_choice.ALT_LOGSUM] = (
            merged.age.to_numpy() + merged.destination.to_numpy()
        )
        return sample

    monkeypatch.setattr(bounded, "_run_destination_logsums", evaluate)
    state = SimpleNamespace(
        filesystem=SimpleNamespace(
            read_model_settings=lambda _: {"location_logsum_rows": 2}
        )
    )
    persons = pd.DataFrame({"age": [10.0, 20.0]}, index=[1, 2])
    sample = pd.DataFrame(
        {"person_id": [2, 2, 2, 1], "destination": [1.0, 2.0, 3.0, 4.0]},
        index=[50, 50, 50, 60],
    )
    expected = evaluate(state, "shopping", persons, sample.copy())
    seen.clear()
    actual = bounded.run_destination_logsums(
        state, "shopping", persons, sample, None, None, 0, "shopping"
    )
    pd.testing.assert_frame_equal(actual, expected)
    assert seen == [3, 1]


def test_trip_pair_logsums_preserve_draws_and_bound_both_joins(monkeypatch):
    seen = []
    offsets = {}

    def evaluate(state, purpose, trips, sample, tours, *args):
        seen.append((len(trips), len(sample)))
        assert set(trips.index) == set(sample.index)
        attributes = trips.join(tours, on="tour_id")
        merged = sample.join(attributes)
        for name in ["od_logsum", "dp_logsum"]:
            for trip in sample.index.unique():
                offsets[trip] = offsets.get(trip, 0) + 1
            sample[name] = merged.age + sample.index.map(offsets)
        return sample

    monkeypatch.setattr(bounded, "_compute_trip_logsums", evaluate)
    state = SimpleNamespace(
        filesystem=SimpleNamespace(
            read_model_settings=lambda _: {"location_logsum_rows": 2}
        )
    )
    trips = pd.DataFrame({"tour_id": [8, 9]}, index=[10, 20])
    tours = pd.DataFrame({"age": [25, 35]}, index=[8, 9])
    sample = pd.DataFrame({"alt_dest": [1, 2, 3, 4]}, index=[10, 10, 10, 20])
    expected = evaluate(state, "work", trips, sample.copy(), tours)
    offsets.clear()
    seen.clear()
    actual = bounded.compute_trip_logsums(
        state, "work", trips, sample, tours, None, None, "work"
    )
    pd.testing.assert_frame_equal(actual, expected)
    assert offsets == {10: 2, 20: 2}
    assert seen == [(1, 3), (1, 1)]
