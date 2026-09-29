"""Walking capability, stable person draws, and actual distance specifications."""

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import sys

import activitysim.abm  # noqa: F401 -- initialize model registry before extensions
from activitysim.core import logit, simulate, workflow
import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).parents[1]
CONFIGS = ROOT / "model/configs"
sys.path.insert(0, str(ROOT))
from extensions.constraint_walk_ability import (  # noqa: E402
    WalkAbilitySettings,
    capability_probabilities,
)


def make_state(output):
    return workflow.State.make_default(
        configs_dir=CONFIGS,
        data_dir=ROOT / "model/data",
        output_dir=Path(output),
        settings={"checkpoints": False, "rng_base_seed": 0},
    )


def run_assignment(persons, output):
    state = make_state(output)
    state.add_table("persons", persons)
    state.get_rn_generator().add_channel("persons", persons)
    state.run.by_name("constraint_walk_ability")
    return state.get_dataframe("persons")


def population(ages, alone=None):
    return pd.DataFrame(
        {
            "age": ages,
            "can_travel_alone": [True] * len(ages) if alone is None else alone,
        },
        index=pd.Index(np.arange(len(ages)) * 7 + 21, name="person_id"),
    )


@pytest.fixture
def settings():
    return WalkAbilitySettings.model_validate(
        yaml.safe_load((CONFIGS / "constraint_walk_ability.yaml").read_text())
    )


def test_age_boundaries_and_adult_override(settings):
    people = population(
        [17, 18, 64, 65, 79, 80, 95], [False, False, True, True, True, True, False]
    )
    assert capability_probabilities(people, settings).tolist() == [
        1,
        0,
        1,
        0.5,
        0.5,
        0.2,
        0,
    ]


@pytest.mark.parametrize(
    "column,value",
    [
        ("age", np.nan),
        ("age", -1),
        ("age", np.inf),
        ("can_travel_alone", None),
        ("can_travel_alone", "false"),
    ],
)
def test_invalid_inputs_rejected(settings, column, value):
    people = population([75])
    people[column] = value
    with pytest.raises(ValueError):
        capability_probabilities(people, settings)


def test_nullable_missing_age_rejected(settings):
    # Pandas nullable numeric dtypes must not let missing ages pass through .all().
    people = population([75])
    people["age"] = pd.array([pd.NA], dtype="Int64")
    with pytest.raises(ValueError, match="ages"):
        capability_probabilities(people, settings)


def test_registered_step_empty_and_persisted(tmp_path):
    people = population([17, 18, 64], [False, False, True])
    result = run_assignment(people, tmp_path / "normal")
    assert result.index.equals(people.index)
    assert result.can_walk_far.tolist() == [True, False, True]
    assert result.walk_distance_limit.tolist() == [np.inf, 0.15, np.inf]
    empty = run_assignment(people.iloc[:0], tmp_path / "empty")
    assert empty.empty and empty.can_walk_far.dtype == bool


def test_draws_repeat_across_order_and_process_partitions(tmp_path):
    people = population([70] * 10000 + [85] * 10000)
    result = run_assignment(people, tmp_path / "all")
    reordered = run_assignment(people.iloc[::-1], tmp_path / "reordered")
    pd.testing.assert_frame_equal(result, reordered.loc[result.index])
    with ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [
            pool.submit(run_assignment, people.iloc[i::2], tmp_path / f"worker{i}")
            for i in range(2)
        ]
        partitioned = pd.concat([f.result() for f in futures]).loc[result.index]
    pd.testing.assert_frame_equal(result, partitioned)
    assert abs(result.loc[result.age == 70, "can_walk_far"].mean() - 0.5) < 0.02
    assert abs(result.loc[result.age == 85, "can_walk_far"].mean() - 0.2) < 0.02


class DistanceSkim:
    def __init__(self, forward, reverse=None):
        self.forward = forward
        self.reverse = forward if reverse is None else reverse

    def __getitem__(self, name):
        return self.forward

    def max(self, name):
        return np.maximum(self.forward, self.reverse)


@pytest.mark.parametrize(
    "filename,tour", [("trip_mode_choice.csv", False), ("tour_mode_choice.csv", True)]
)
def test_actual_mode_spec_boundaries_and_probabilities(tmp_path, filename, tour):
    state = make_state(tmp_path)
    spec = state.filesystem.read_model_spec(filename)
    spec = spec[
        spec.index.get_level_values("Label").str.startswith("util_person_walk")
    ].astype(float)
    distances = pd.Series([0.149, 0.15, 0.151, 0.151, 0.10])
    reverse = pd.Series([0.149, 0.15, 0.151, 0.151, 0.20])
    people = pd.DataFrame({"walk_distance_limit": [0.15, 0.15, 0.15, np.inf, 0.15]})
    local = {
        "od_skims": DistanceSkim(distances, reverse),
        "odt_skims": DistanceSkim(distances * 60 / 3),
        "dot_skims": DistanceSkim(reverse * 60 / 3),
        "walkSpeed": 3,
        "WALK_TRANSIT_WALK_MINUTES_PER_UNIT": 1,
    }
    spec.index = spec.index.get_level_values("Expression")
    variables = simulate.eval_variables(state, spec.index, people, local)
    utilities = variables.dot(spec)
    probs = logit.utils_to_probs(state, utilities)
    expected = [False, False, True, False, tour]
    for mode in ["WALK", "WALK_TRANSIT"]:
        assert (utilities[mode] == -999).tolist() == expected
        assert (probs[mode] == 0).tolist() == expected
    assert (probs.RIDEHAIL > 0).all()


@pytest.mark.parametrize(
    "filename", ["trip_destination_sample.csv", "trip_destination.csv"]
)
def test_actual_destination_specs_check_both_legs(tmp_path, filename):
    state = make_state(tmp_path)
    spec = state.filesystem.read_model_spec(filename)
    expressions = spec.index.get_level_values("Expression")
    spec = spec[expressions.str.contains("df.walk_distance_limit", regex=False)]
    # Resolve the same configured unavailability coefficient as destination choice.
    spec = spec.replace("coef_UNAVAILABLE", -999).astype(float)
    people = pd.DataFrame(
        {
            "tour_mode_is_walk": [True, True, True, True, False],
            "walk_distance_limit": [0.15, 0.15, 0.15, np.inf, 0.15],
        }
    )
    local = {
        "od_skims": DistanceSkim(pd.Series([0.15, 0.151, 0.10, 0.20, 0.20])),
        "dp_skims": DistanceSkim(pd.Series([0.15, 0.10, 0.151, 0.20, 0.20])),
    }
    spec.index = spec.index.get_level_values("Expression")
    variables = simulate.eval_variables(state, spec.index, people, local)
    utilities = variables.dot(spec)
    assert utilities.work.tolist() == [0, -999, -999, 0, 0]


def test_workflow_order_and_chooser_columns():
    for path in [CONFIGS / "settings.yaml", ROOT / "model/configs_mp/settings.yaml"]:
        models = yaml.safe_load(path.read_text())["models"]
        assert (
            models.index("constraint_can_travel_alone")
            < models.index("constraint_walk_ability")
            < models.index("school_location")
        )
        assert models.index("constraint_walk_ability") < models.index(
            "workplace_location"
        )
    for filename, key in [
        ("tour_mode_choice.yaml", "LOGSUM_CHOOSER_COLUMNS"),
        ("trip_mode_choice.yaml", "TOURS_MERGED_CHOOSER_COLUMNS"),
    ]:
        assert (
            "walk_distance_limit"
            in yaml.safe_load((CONFIGS / filename).read_text())[key]
        )
