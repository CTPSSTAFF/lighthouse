"""Avoid broadcasting unused person attributes onto every tour for stop frequency."""

import logging

import pandas as pd
from activitysim.abm.models.stop_frequency import (
    StopFrequencySettings,
    stop_frequency as _stop_frequency,
)
from activitysim.abm.tables.util import simple_table_join
from activitysim.core import los, workflow

logger = logging.getLogger("activitysim.extensions.projected_stop_frequency")


@workflow.step(overloading=True)
def stop_frequency(
    state: workflow.State,
    tours: pd.DataFrame,
    stop_frequency_alts: pd.DataFrame,
    network_los: los.Network_LOS,
    model_settings: StopFrequencySettings | None = None,
    model_settings_file_name: str = "stop_frequency.yaml",
    trace_label: str = "stop_frequency",
) -> None:
    settings = state.filesystem.read_model_settings("laptop_memory.yaml") or {}
    columns = settings.get("stop_frequency_person_columns")
    if columns is None:
        merged = state.get_dataframe("tours_merged")
    else:
        # Keep every tour: the upstream preprocessor counts tours by household
        # and person before choosing stops. Only prune unused right-side columns.
        columns = [column for column in columns if column not in tours.columns]
        persons = state.get_dataframe("persons_merged", columns=columns)
        merged = simple_table_join(tours, persons, left_on="person_id")
        del persons
        logger.info(
            "Stop frequency: %s tours, %s projected columns",
            len(merged),
            len(merged.columns),
        )
    _stop_frequency(
        state,
        tours,
        merged,
        stop_frequency_alts,
        network_los,
        model_settings=model_settings,
        model_settings_file_name=model_settings_file_name,
        trace_label=trace_label,
    )
