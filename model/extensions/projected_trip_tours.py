"""Build trip-model tour joins from the configured chooser columns."""

import logging

import pandas as pd
from activitysim.abm.tables.tours import tours_merged as _upstream_tours_merged  # noqa: F401
from activitysim.abm.tables.util import simple_table_join
from activitysim.core import workflow

logger = logging.getLogger("activitysim.extensions.projected_trip_tours")
TRIP_MODELS = {"trip_destination", "trip_purpose_and_destination", "trip_mode_choice"}


def join_tour_attributes(tours, persons, columns=None):
    if columns is not None:
        columns = [column for column in columns if column not in tours.columns]
        persons = persons[columns]
    return simple_table_join(tours, persons, left_on="person_id")


@workflow.step(cache=True, kind="temp_table", overloading=True, copy_tables=False)
def tours_merged(
    state: workflow.State, tours: pd.DataFrame, persons_merged: pd.DataFrame
):
    # This pure join never mutates its inputs, so the workflow need not copy
    # the complete person and tour tables before calling it.
    settings = state.filesystem.read_model_settings("laptop_memory.yaml") or {}
    columns = None
    if (
        settings.get("project_trip_tours", False)
        and state.current_model_name in TRIP_MODELS
    ):
        mode = state.filesystem.read_model_settings("trip_mode_choice.yaml")
        destination = state.filesystem.read_model_settings("trip_destination.yaml")
        logsum = state.filesystem.read_model_settings(destination["LOGSUM_SETTINGS"])
        columns = list(
            dict.fromkeys(
                mode["TOURS_MERGED_CHOOSER_COLUMNS"]
                + logsum["TOURS_MERGED_CHOOSER_COLUMNS"]
            )
        )
        logger.info(
            "%s: projecting tour attributes before the trip-model join",
            state.current_model_name,
        )
    # Retain all tour columns, including origin/destination used before the
    # upstream trip-destination code filters to logsum chooser columns.
    return join_tour_attributes(tours, persons_merged, columns)
