"""Projection retains complete tour groups and the upstream choice implementation."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "model"))
from extensions import projected_stop_frequency as projected  # noqa: E402


@pytest.mark.parametrize("laptop", [True, False])
def test_projection_preserves_tours_and_left_column_precedence(monkeypatch, laptop):
    tours = pd.DataFrame(
        {
            "person_id": [3, 3, 4],
            "household_id": [1, 1, 2],
            "female": [True, True, False],
        },
        index=[10, 20, 30],
    )
    persons = pd.DataFrame(
        {"female": [False, True], "income": [10.0, 20.0], "unused": [100, 200]},
        index=[3, 4],
    )
    full = projected.simple_table_join(tours, persons, "person_id")
    calls = []

    def dataframe(name, columns=None):
        calls.append((name, columns))
        return (persons[columns] if name == "persons_merged" else full).copy()

    state = SimpleNamespace(
        filesystem=SimpleNamespace(
            read_model_settings=lambda _: (
                {"stop_frequency_person_columns": ["female", "income"]}
                if laptop
                else {}
            )
        ),
        get_dataframe=dataframe,
    )
    received = []
    monkeypatch.setattr(
        projected,
        "_stop_frequency",
        lambda state, tours, merged, *a, **kw: received.append(merged),
    )
    projected.stop_frequency(state, tours, None, None)
    expected = full.drop(columns="unused") if laptop else full
    pd.testing.assert_frame_equal(received[0], expected)
    assert received[0].groupby("person_id").size().to_dict() == {3: 2, 4: 1}
    assert calls == (
        [("persons_merged", ["income"])] if laptop else [("tours_merged", None)]
    )
