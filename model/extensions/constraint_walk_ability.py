"""Assign persistent person-level walking capability from scenario assumptions."""

import logging

import numpy as np
import pandas as pd
from pydantic import Field

from activitysim.core import tracing, workflow
from activitysim.core.configuration.base import PydanticReadable

logger = logging.getLogger("activitysim")


class WalkAbilitySettings(PydanticReadable, extra="forbid"):
    LIMITED_WALK_DISTANCE: float = Field(gt=0, allow_inf_nan=False)
    ADULT_AGE: int = Field(ge=0)
    PROBABILITY_65_79: float = Field(ge=0, le=1)
    PROBABILITY_80_PLUS: float = Field(ge=0, le=1)


def capability_probabilities(persons, settings):
    """Return age probabilities with the adult travel-alone override applied."""
    if not persons.index.is_unique or persons.index.hasnans:
        raise ValueError("Walking capability requires unique, nonmissing person IDs")
    age = persons["age"]
    if (
        not pd.api.types.is_numeric_dtype(age)
        or age.isna().any()
        or not (np.isfinite(age) & (age >= 0)).all()
    ):
        raise ValueError("Walking capability requires nonmissing, nonnegative ages")
    alone = persons["can_travel_alone"]
    if not pd.api.types.is_bool_dtype(alone) or alone.isna().any():
        raise ValueError("can_travel_alone must contain nonmissing booleans")
    probability = pd.Series(1.0, index=persons.index)
    probability.loc[(age >= 65) & (age < 80)] = settings.PROBABILITY_65_79
    probability.loc[age >= 80] = settings.PROBABILITY_80_PLUS
    probability.loc[(age >= settings.ADULT_AGE) & ~alone] = 0.0
    return probability


@workflow.step
def constraint_walk_ability(
    state: workflow.State,
    persons: pd.DataFrame,
    model_settings: WalkAbilitySettings | None = None,
    model_settings_file_name: str = "constraint_walk_ability.yaml",
    trace_label: str = "constraint_walk_ability",
) -> None:
    if model_settings is None:
        model_settings = WalkAbilitySettings.read_settings_file(
            state.filesystem, model_settings_file_name
        )
    probability = capability_probabilities(persons, model_settings)
    persons = persons.copy()
    if len(persons):
        draws = state.get_rn_generator().random_for_df(persons).reshape(-1)
        persons["can_walk_far"] = draws < probability.to_numpy()
    else:
        persons["can_walk_far"] = pd.Series(False, index=persons.index, dtype=bool)
    # Infinity leaves existing mode-specific distance rules in control for capable people.
    persons["walk_distance_limit"] = np.where(
        persons.can_walk_far, np.inf, model_settings.LIMITED_WALK_DISTANCE
    )
    state.add_table("persons", persons)
    tracing.print_summary("can_walk_far", persons.can_walk_far, value_counts=True)
    logger.info("Walking capability: %s", persons.can_walk_far.value_counts().to_dict())
    state.tracing.trace_df(persons, label=trace_label, warn_if_empty=True)
