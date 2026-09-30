"""Compiled low-utility alternatives must remain viable, without enabling -999 alts."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "model"))
from extensions.stable_probabilities import utils_to_probs, _utils_to_probs  # noqa: E402


@pytest.mark.parametrize(
    "utilities", [[-127, -128, -999], [-110, -111, -999], [-999, -999, -999]]
)
def test_zero_probability_path_matches_float64(utilities):
    state = SimpleNamespace(settings=SimpleNamespace(skip_failed_choices=False))
    values = pd.DataFrame([utilities], dtype=np.float32)
    kwargs = dict(allow_zero_probs=True, overflow_protection=False, return_logsums=True)
    actual, actual_logsums = utils_to_probs(state, values, **kwargs)
    expected, expected_logsums = _utils_to_probs(
        state, values.astype(np.float64), **kwargs
    )
    pd.testing.assert_frame_equal(actual, expected)
    pd.testing.assert_series_equal(actual_logsums, expected_logsums)
    if utilities[0] != -999:
        assert actual.iloc[0, 0] > 0
        assert actual.iloc[0, -1] == 0
    else:
        assert (actual == 0).all().all()
