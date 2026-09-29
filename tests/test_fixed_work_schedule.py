"""Real MNL configuration, eligibility, person draws, and persistence."""

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import sys

import activitysim.abm  # noqa: F401
from activitysim.core import workflow
import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).parents[1]
CONFIGS = ROOT / "model/configs"
sys.path.insert(0, str(ROOT / "model"))
from extensions.constraint_fixed_work_schedule import (  # noqa: E402
    FixedWorkScheduleSettings,
    prepare_choosers,
)


def settings():
    return FixedWorkScheduleSettings.model_validate(
        yaml.safe_load((CONFIGS / "constraint_fixed_work_schedule.yaml").read_text())
    )


def population(n=8):
    ids = pd.Index(np.arange(n) * 7 + 21, name="person_id")
    persons = pd.DataFrame(
        {
            "household_id": np.arange(n) // 2 + 100,
            "pemploy": 1,
            "fixed_schedule_source_pstudent": 3,
            "ptype": 1,
            "is_student": False,
            "naics_code": 722,
            "is_out_of_home_worker": True,
        },
        index=ids,
    )
    households = pd.DataFrame(
        {"income": 100000.0, "num_workers": 0},
        index=pd.Index(persons.household_id.unique(), name="household_id"),
    )
    return persons, households


def run_assignment(persons, households, output, explicit=False, configs=CONFIGS):
    state = workflow.State.make_default(
        configs_dir=configs,
        data_dir=ROOT / "model/data",
        output_dir=Path(output),
        settings={
            "checkpoints": False,
            "rng_base_seed": 0,
            "use_explicit_error_terms": explicit,
        },
    )
    state.add_table("persons", persons)
    state.add_table("households", households)
    state.get_rn_generator().add_channel("persons", persons)
    state.run.by_name("constraint_fixed_work_schedule")
    pd.testing.assert_frame_equal(state.get_dataframe("households"), households)
    return state.get_dataframe("persons")


def test_eligibility_and_all_worker_denominator(tmp_path):
    people, households = population()
    people.loc[21, "is_out_of_home_worker"] = False
    # Source student recoded to nonstudent by initialization; still excluded.
    people.loc[28, "fixed_schedule_source_pstudent"] = 2
    people.loc[35, "pemploy"] = 3
    people.loc[42, "ptype"] = 3
    people.loc[49, "is_student"] = True
    people.loc[56, "pemploy"] = 2
    result = run_assignment(people, households, tmp_path)
    assert result.works_fixed_schedule.notna().tolist() == [
        True,
        False,
        False,
        False,
        False,
        True,
        True,
        True,
    ]
    assert result.loc[21, "fixed_schedule_income_proxy"] == 50000
    assert result.loc[21, "fixed_schedule_household_workers"] == 2
    assert result.loc[21, "fixed_schedule_probability"] == pytest.approx(0.5)
    assert result.loc[28, "fixed_schedule_status"] == "not_applicable_student"
    assert result.loc[35, "fixed_schedule_status"] == "not_applicable_nonworker"
    assert str(result.works_fixed_schedule.dtype) == "boolean"
    path = tmp_path / "persons.parquet"
    result.to_parquet(path)
    pd.testing.assert_frame_equal(result, pd.read_parquet(path))


@pytest.mark.parametrize(
    "column,value",
    [
        ("pemploy", np.nan),
        ("pemploy", 7),
        ("fixed_schedule_source_pstudent", np.nan),
        ("is_student", None),
        ("ptype", 99),
        ("naics_code", 99),
        ("household_id", -1),
    ],
)
def test_invalid_person_inputs(column, value):
    people, households = population()
    people.loc[21, column] = value
    with pytest.raises(ValueError):
        prepare_choosers(people, households, settings())


def test_income_errors_flooring_and_zero():
    people, households = population()
    households.loc[100, "income"] = np.nan
    with pytest.raises(ValueError, match="income"):
        prepare_choosers(people, households, settings())
    households.loc[100, "income"] = -100
    households.loc[101, "income"] = 0
    chooser, _ = prepare_choosers(people, households, settings())
    assert chooser.loc[21, "fixed_schedule_income_proxy"] == -50
    assert chooser.loc[21, "fixed_schedule_income_term"] == pytest.approx(-np.log(2))
    assert chooser.loc[35, "fixed_schedule_income_term"] == pytest.approx(-np.log(2))


def test_excluded_people_do_not_require_income_or_industry(tmp_path):
    people, households = population()
    people.pemploy = 3
    people.naics_code = np.nan
    households.income = np.nan
    result = run_assignment(people, households, tmp_path / "excluded")
    assert result.works_fixed_schedule.isna().all()
    empty = run_assignment(people.iloc[:0], households.iloc[:0], tmp_path / "empty")
    assert empty.empty
    assert str(empty.works_fixed_schedule.dtype) == "boolean"


def test_real_spec_industry_anchors_and_income_response(tmp_path):
    people, households = population(50)
    codes = settings().INDUSTRY_CODES
    people.naics_code = np.repeat(codes, 2)
    result = run_assignment(people, households, tmp_path / "reference")
    anchors = [
        0.4,
        0.65,
        0.7,
        0.75,
        0.8,
        0.8,
        0.8,
        0.6,
        0.55,
        0.55,
        0.65,
        0.75,
        0.3,
        0.4,
        0.3,
        0.25,
        0.35,
        0.65,
        0.8,
        0.7,
        0.4,
        0.6,
        0.5,
        0.55,
        0.65,
    ]
    np.testing.assert_allclose(result.fixed_schedule_probability, np.repeat(anchors, 2))
    lower = run_assignment(people, households.assign(income=50000), tmp_path / "low")
    higher = run_assignment(people, households.assign(income=200000), tmp_path / "high")
    assert (lower.fixed_schedule_probability > result.fixed_schedule_probability).all()
    assert (higher.fixed_schedule_probability < result.fixed_schedule_probability).all()
    retail_food = result.naics_code.eq(722)
    assert lower.loc[retail_food, "fixed_schedule_probability"].iloc[
        0
    ] == pytest.approx(4 / 7)
    assert higher.loc[retail_food, "fixed_schedule_probability"].iloc[
        0
    ] == pytest.approx(0.4)


def test_repeatability_order_transport_and_process_partitions(tmp_path):
    people, households = population(10000)
    result = run_assignment(people, households, tmp_path / "all")
    reordered = run_assignment(
        people.iloc[::-1], households.iloc[::-1], tmp_path / "reorder"
    )
    pd.testing.assert_frame_equal(result, reordered.loc[result.index])
    # Remote status cannot alter the utility or random assignment.
    changed = run_assignment(
        people.assign(is_out_of_home_worker=False), households, tmp_path / "remote"
    )
    pd.testing.assert_series_equal(
        result.works_fixed_schedule, changed.works_fixed_schedule
    )
    with ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = []
        for i in range(2):
            hh = households.iloc[i::2]
            pp = people.loc[people.household_id.isin(hh.index)]
            futures.append(pool.submit(run_assignment, pp, hh, tmp_path / f"worker{i}"))
        partitioned = pd.concat([f.result() for f in futures]).loc[result.index]
    pd.testing.assert_frame_equal(result, partitioned)
    assert abs(result.works_fixed_schedule.mean() - 0.5) < 0.02


def test_explicit_error_terms(tmp_path):
    people, households = population()
    result = run_assignment(people, households, tmp_path, explicit=True)
    assert result.works_fixed_schedule.notna().all()
    np.testing.assert_allclose(result.fixed_schedule_probability, 0.5)


def test_zero_income_coefficient_and_alternative_order(tmp_path):
    # Alternative position must come from its name, not an assumed Boolean index.
    override = tmp_path / "configs"
    override.mkdir()
    spec = pd.read_csv(CONFIGS / "constraint_fixed_work_schedule.csv", comment="#")
    spec[["Label", "Description", "Expression", "other", "fixed"]].to_csv(
        override / "constraint_fixed_work_schedule.csv", index=False
    )
    coeff = pd.read_csv(
        CONFIGS / "constraint_fixed_work_schedule_coefficients.csv", comment="#"
    )
    coeff.loc[coeff.coefficient_name.eq("coef_income"), "value"] = 0
    coeff.to_csv(
        override / "constraint_fixed_work_schedule_coefficients.csv", index=False
    )
    people, households = population(10000)
    people.naics_code = 61
    result = run_assignment(
        people,
        households.assign(income=0),
        tmp_path / "zero",
        configs=[override, CONFIGS],
    )
    np.testing.assert_allclose(result.fixed_schedule_probability, 0.8)
    assert abs(result.works_fixed_schedule.mean() - 0.8) < 0.02
    higher = run_assignment(
        people,
        households.assign(income=1000000),
        tmp_path / "million",
        configs=[override, CONFIGS],
    )
    pd.testing.assert_series_equal(
        result.works_fixed_schedule, higher.works_fixed_schedule
    )


def test_duplicate_person_and_household_ids():
    people, households = population()
    with pytest.raises(ValueError, match="persons requires unique"):
        prepare_choosers(pd.concat([people, people.iloc[:1]]), households, settings())
    with pytest.raises(ValueError, match="households requires unique"):
        prepare_choosers(
            people, pd.concat([households, households.iloc[:1]]), settings()
        )
