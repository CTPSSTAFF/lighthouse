"""Avoid float32 underflow in ActivitySim's zero-probability choice path.

ActivitySim 1.6 disables utility shifting when allow_zero_probs is set. Compiled
utilities can be float32, where exp(-127) is zero; the reference evaluator uses
float64 and retains that viable alternative. Promote only this probability
conversion, leaving skim storage and compiled utility evaluation unchanged.
"""

from functools import wraps

import numpy as np
from activitysim.core import logit

_utils_to_probs = logit.utils_to_probs


@wraps(_utils_to_probs)
def utils_to_probs(
    state,
    utils,
    trace_label=None,
    exponentiated=False,
    allow_zero_probs=False,
    trace_choosers=None,
    overflow_protection=True,
    return_logsums=False,
):
    """Retain finite low utilities while preserving genuinely unavailable choices."""
    if allow_zero_probs and utils.values.dtype == np.float32:
        utils = utils.astype(np.float64)
    return _utils_to_probs(
        state,
        utils,
        trace_label=trace_label,
        exponentiated=exponentiated,
        allow_zero_probs=allow_zero_probs,
        trace_choosers=trace_choosers,
        overflow_protection=overflow_protection,
        return_logsums=return_logsums,
    )


logit.utils_to_probs = utils_to_probs
