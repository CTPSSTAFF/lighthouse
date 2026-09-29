"""Prototype recurring work-schedule status; does not schedule work hours."""

import logging
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import Field

from activitysim.core import logit, simulate, workflow
from activitysim.core.configuration.logit import LogitComponentSettings

logger = logging.getLogger("activitysim")


class FixedWorkScheduleSettings(LogitComponentSettings, extra="forbid"):
    LOGIT_TYPE: Literal["MNL"] = "MNL"
    FIXED_ALT: str = "fixed"
    OTHER_ALT: str = "other"
    INDUSTRY_CODES: list[int]
    EMPLOYED_CODES: list[int]
    EMPLOYMENT_CODES: list[int]
    STUDENT_CODES: list[int]
    STUDENT_STATUS_CODES: list[int]
    STUDENT_PERSON_TYPES: list[int]
    PERSON_TYPES: list[int]
    INCOME_SCALE: float = Field(gt=0, allow_inf_nan=False)
    REFERENCE_INCOME: float = Field(ge=0, allow_inf_nan=False)


def _numeric(frame, column):
    """Reject missing/nonfinite inputs with the affected IDs in the error."""
    values = pd.to_numeric(frame[column], errors="coerce")
    bad = values.isna() | ~np.isfinite(values)
    if bad.any():
        raise ValueError(f"Invalid {column} for IDs {frame.index[bad].tolist()[:10]}")
    return values


def _coded(frame, column, allowed):
    values = _numeric(frame, column)
    bad = ~values.isin(allowed)
    if bad.any():
        raise ValueError(f"Unknown {column} for IDs {frame.index[bad].tolist()[:10]}")
    return values


def prepare_choosers(persons, households, settings):
    """Build eligible choosers and a component-local count of ALL employed members."""
    for name, frame in (("persons", persons), ("households", households)):
        if not frame.index.is_unique or frame.index.hasnans:
            raise ValueError(f"{name} requires unique, nonmissing IDs")
    if not persons.household_id.isin(households.index).all():
        raise ValueError("Persons have missing or unknown household IDs")
    employed = _coded(persons, "pemploy", settings.EMPLOYMENT_CODES).isin(
        settings.EMPLOYED_CODES
    )
    source_student = _coded(
        persons, "fixed_schedule_source_pstudent", settings.STUDENT_STATUS_CODES
    ).isin(settings.STUDENT_CODES)
    person_type = _coded(persons, "ptype", settings.PERSON_TYPES)
    current_student = persons.is_student
    if not pd.api.types.is_bool_dtype(current_student) or current_student.isna().any():
        raise ValueError("is_student must contain nonmissing booleans")
    student = (
        source_student
        | current_student
        | person_type.isin(settings.STUDENT_PERSON_TYPES)
    )
    eligible = employed & ~student
    status = pd.Series("not_applicable_nonworker", index=persons.index)
    status.loc[student] = "not_applicable_student"
    status.loc[eligible] = "prototype_logit"
    choosers = persons.loc[eligible].copy()
    choosers["naics_code"] = _coded(choosers, "naics_code", settings.INDUSTRY_CODES)
    counts = employed.groupby(persons.household_id).sum()
    choosers["fixed_schedule_household_workers"] = choosers.household_id.map(counts)
    if (choosers.fixed_schedule_household_workers <= 0).any():
        raise ValueError("Eligible worker has no employed household members")
    income = households.loc[choosers.household_id.unique(), ["income"]].copy()
    income["income"] = _numeric(income, "income")
    choosers["fixed_schedule_income_proxy"] = (
        choosers.household_id.map(income.income)
        / choosers.fixed_schedule_household_workers
    )
    negative = choosers.fixed_schedule_income_proxy < 0
    logger.info("Fixed schedule: flooring %d negative income proxies", negative.sum())
    choosers["fixed_schedule_income_term"] = np.log1p(
        choosers.fixed_schedule_income_proxy.clip(lower=0) / settings.INCOME_SCALE
    ) - np.log1p(settings.REFERENCE_INCOME / settings.INCOME_SCALE)
    return choosers, status


@workflow.step
def constraint_fixed_work_schedule(
    state: workflow.State,
    persons: pd.DataFrame,
    households: pd.DataFrame,
    model_settings: FixedWorkScheduleSettings | None = None,
    model_settings_file_name: str = "constraint_fixed_work_schedule.yaml",
    trace_label: str = "constraint_fixed_work_schedule",
) -> None:
    """Assign recurring fixed status, retaining eligibility and income provenance."""
    settings = model_settings or FixedWorkScheduleSettings.read_settings_file(
        state.filesystem, model_settings_file_name
    )
    choosers, status = prepare_choosers(persons, households, settings)
    spec = state.filesystem.read_model_spec(file_name=settings.SPEC)
    if len(spec.columns) != 2 or set(spec.columns) != {
        settings.FIXED_ALT,
        settings.OTHER_ALT,
    }:
        raise ValueError(
            "Fixed-schedule specification must have fixed and other alternatives"
        )
    coefficients = state.filesystem.read_model_coefficients(settings)
    spec = simulate.eval_coefficients(state, spec, coefficients, estimator=None)
    if not np.isfinite(spec.to_numpy()).all():
        raise ValueError("Fixed-schedule specification has nonfinite coefficients")
    fixed_position = spec.columns.get_loc(settings.FIXED_ALT)
    probability = pd.Series(np.nan, index=choosers.index, dtype=float)

    def capture_probability(state, values, chunk, spec, trace_label):
        # Use the framework's normal chooser, retaining its actual probabilities.
        explicit = state.settings.use_explicit_error_terms
        probs = logit.utils_to_probs(state, values) if explicit else values
        if not np.isfinite(probs.to_numpy()).all():
            raise ValueError("Fixed-schedule model produced nonfinite probabilities")
        probability.loc[chunk.index] = probs[settings.FIXED_ALT]
        if explicit:
            return logit.make_choices_utility_based(
                state, values, trace_label=trace_label
            )
        return logit.make_choices(state, probs, trace_label=trace_label)

    choices = pd.Series(index=choosers.index, dtype="int64")
    if not choosers.empty:
        choices = simulate.simple_simulate(
            state,
            choosers=choosers,
            spec=spec,
            nest_spec=None,
            locals_d=settings.CONSTANTS,
            custom_chooser=capture_probability,
            trace_label=trace_label,
            trace_choice_name="works_fixed_schedule",
            compute_settings=settings.compute_settings,
        )
    if (
        not choices.index.is_unique
        or len(choices) != len(choosers)
        or not choosers.index.isin(choices.index).all()
        or not choices.isin([0, 1]).all()
        or probability.isna().any()
    ):
        raise ValueError("Incomplete or invalid fixed-schedule predictions")
    result = persons.copy()
    result["works_fixed_schedule"] = pd.Series(
        pd.NA, index=persons.index, dtype="boolean"
    )
    result.loc[choices.index, "works_fixed_schedule"] = choices.eq(fixed_position)
    result["fixed_schedule_status"] = status
    result["fixed_schedule_probability"] = probability.reindex(persons.index)
    for column in (
        "fixed_schedule_household_workers",
        "fixed_schedule_income_proxy",
        "fixed_schedule_income_term",
    ):
        result[column] = choosers[column].reindex(persons.index)
    state.add_table("persons", result)
    logger.info("Fixed schedule status: %s", status.value_counts().to_dict())
    if not choosers.empty:
        summary = choosers[["naics_code", "fixed_schedule_income_proxy"]].copy()
        summary["probability"] = probability
        summary["fixed"] = choices.eq(fixed_position)
        summary["income_band"] = pd.cut(
            summary.fixed_schedule_income_proxy,
            [-np.inf, 25000, 50000, 100000, np.inf],
        )
        logger.info(
            "Fixed schedule industry/income summary:\n%s",
            summary.groupby(["naics_code", "income_band"], observed=True)
            .agg(
                persons=("fixed", "size"),
                expected=("probability", "sum"),
                assigned=("fixed", "sum"),
            )
            .to_string(),
        )
    state.tracing.trace_df(result, label=trace_label, warn_if_empty=True)
