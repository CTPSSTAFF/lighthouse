"""Bound person/sample joins that precede ActivitySim's internal chunking."""

from functools import wraps
import logging

import numpy as np
from activitysim.abm.models import location_choice, trip_destination
from activitysim.abm.models.util import tour_destination

logger = logging.getLogger("activitysim.extensions.bounded_location_logsums")
_run_location_logsums = location_choice.run_location_logsums
_run_destination_logsums = tour_destination.run_destination_logsums
_compute_trip_logsums = trip_destination.compute_logsums


def _bounded(state, sample, evaluate, trace_label, columns=None):
    columns = columns or [location_choice.ALT_LOGSUM]
    settings = state.filesystem.read_model_settings("laptop_memory.yaml") or {}
    rows = int(settings.get("location_logsum_rows", 0))
    if rows <= 0 or len(sample) <= rows:
        return evaluate(sample)

    # Preprocessors consume broadcast random draws once per chooser. Keep every
    # chooser's alternatives together so batching preserves those RNG offsets.
    # Slice and assign positionally to preserve duplicate-index row order.
    if not sample.index.is_monotonic_increasing:
        raise ValueError("Bounded logsum samples must be sorted by chooser ID")
    logger.info(
        "%s: bounding %s sampled rows to joins of %s", trace_label, len(sample), rows
    )
    values = None
    start = 0
    while start < len(sample):
        stop = min(start + rows, len(sample))
        if stop < len(sample):
            stop = sample.index.searchsorted(sample.index[stop - 1], side="right")
        batch = sample.iloc[start:stop].copy()
        result = evaluate(batch)
        part = result[columns].to_numpy()
        if values is None:
            values = np.empty((len(sample), len(columns)), dtype=part.dtype)
        values[start:stop] = part
        del batch, result, part
        start = stop
    sample[columns] = values
    return sample


@wraps(_run_location_logsums)
def run_location_logsums(
    state,
    segment_name,
    persons_merged_df,
    network_los,
    location_sample_df,
    model_settings,
    chunk_size,
    chunk_tag,
    trace_label,
):
    def evaluate(sample):
        return _run_location_logsums(
            state,
            segment_name,
            persons_merged_df,
            network_los,
            sample,
            model_settings,
            chunk_size,
            chunk_tag,
            trace_label,
        )

    return _bounded(state, location_sample_df, evaluate, trace_label)


@wraps(_run_destination_logsums)
def run_destination_logsums(
    state,
    tour_purpose,
    persons_merged,
    destination_sample,
    model_settings,
    network_los,
    chunk_size,
    trace_label,
):
    def evaluate(sample):
        return _run_destination_logsums(
            state,
            tour_purpose,
            persons_merged,
            sample,
            model_settings,
            network_los,
            chunk_size,
            trace_label,
        )

    return _bounded(state, destination_sample, evaluate, trace_label)


location_choice.run_location_logsums = run_location_logsums
tour_destination.run_destination_logsums = run_destination_logsums


@wraps(_compute_trip_logsums)
def compute_trip_logsums(
    state,
    primary_purpose,
    trips,
    destination_sample,
    tours_merged,
    model_settings,
    skim_hotel,
    trace_label,
):
    def evaluate(sample):
        # Bound both joins: trip attributes first, then sampled alternatives.
        batch_trips = trips.loc[sample.index.unique()]
        return _compute_trip_logsums(
            state,
            primary_purpose,
            batch_trips,
            sample,
            tours_merged,
            model_settings,
            skim_hotel,
            trace_label,
        )

    return _bounded(
        state,
        destination_sample,
        evaluate,
        trace_label,
        columns=["od_logsum", "dp_logsum"],
    )


trip_destination.compute_logsums = compute_trip_logsums
