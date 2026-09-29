"""Actual skim lookups must respect zone IDs with either execution backend."""

from pathlib import Path
import sys
import uuid

import activitysim.abm  # noqa: F401
from activitysim.core import workflow
import numpy as np
import openmatrix as omx
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import extensions  # noqa: E402, F401 -- register runtime setup used by the CLI


@pytest.mark.parametrize("sharrow", [False, "require"])
def test_unsorted_omx_ids_and_directional_periods(tmp_path, sharrow):
    config = tmp_path / "configs"
    data = tmp_path / "data"
    config.mkdir()
    data.mkdir()
    # Three distinct orders: source land use, sorted IDs, and OMX storage.
    pd.DataFrame({"zone_id": [30, 10, 20]}).to_csv(data / "land_use.csv", index=False)
    raw = np.array(
        [[2020, 2030, 2010], [3020, 3030, 3010], [1020, 1030, 1010]], dtype=np.float32
    )
    with omx.open_file(str(data / "skims.omx"), "w") as skims:
        skims["dist_nm"] = raw
        skims["time__AM"] = raw + 10000
        skims["time__PM"] = raw + 20000
        skims.create_mapping("ID", [20, 30, 10])
    (config / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "inherit_settings": True,
                "multiprocess": False,
                "input_table_list": [
                    {
                        "tablename": "land_use",
                        "filename": "land_use.csv",
                        "index_col": "zone_id",
                        "recode_columns": {"zone_id": "zero-based"},
                    }
                ],
            }
        )
    )
    (config / "network_los.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "test_" + uuid.uuid4().hex,
                "zone_system": 1,
                "taz_skims": ["skims.omx"],
                "skim_time_periods": {
                    "period_minutes": 60,
                    "time_window": 1440,
                    "periods": [0, 12, 24],
                    "labels": ["AM", "PM"],
                },
            }
        )
    )
    configs = [config]
    if sharrow:
        configs.append(ROOT / "model/configs_sh")
    configs.append(ROOT / "model/configs")
    state = workflow.State.make_default(
        configs_dir=configs, data_dir=data, output_dir=tmp_path / "output"
    )
    assert state.settings.sharrow == sharrow
    assert state.settings.recode_pipeline_columns == bool(sharrow)
    land_use = state.get_dataframe("land_use")
    mapping = (
        dict(zip(land_use["_original_zone_id"], land_use.index))
        if sharrow
        else {i: i for i in land_use.index}
    )
    skim = state.get_injectable("network_los").get_default_skim_dict()
    origins = np.array([mapping[30], mapping[10]])
    destinations = np.array([mapping[10], mapping[20]])
    np.testing.assert_array_equal(
        skim.lookup(origins, destinations, "dist_nm"), [3010, 1020]
    )
    frame = pd.DataFrame(
        {"origin": origins, "destination": destinations, "period": ["AM", "PM"]}
    )
    wrapper = skim.wrap_3d("origin", "destination", "period")
    wrapper.set_df(frame)
    np.testing.assert_array_equal(wrapper["time"], [13010, 21020])


@pytest.mark.parametrize("sharrow", [False, "require"])
def test_school_bus_missing_distance_has_same_utility(tmp_path, sharrow):
    from activitysim.core import simulate
    from activitysim.core.configuration.logit import LogitComponentSettings
    import xarray as xr

    state = workflow.State.make_default(
        configs_dir=ROOT / "model/configs",
        data_dir=ROOT / "model/data",
        output_dir=tmp_path / "output",
        settings={"sharrow": sharrow},
    )
    state.filesystem.sharrow_cache_dir = tmp_path / "compiled"
    # This specification has no spatial lookups; isolate expression semantics
    # from skim loading, which is exercised by the shuffled-OMX test above.
    state.set("skim_dataset", xr.Dataset())
    settings = LogitComponentSettings.read_settings_file(
        state.filesystem, "constraint_school_bus_availability.yaml"
    )
    coefficients = state.filesystem.read_model_coefficients(settings)
    spec = simulate.eval_coefficients(
        state, state.filesystem.read_model_spec(settings.SPEC), coefficients, None
    )
    people = pd.DataFrame(
        {
            "age": [18] * 4,
            "school_segment": [0] * 4,
            "distance_to_school": [np.nan, 1.0, 3.0, np.inf],
            "home_is_urban": [False] * 4,
            "home_is_rural": [False] * 4,
            "auto_ownership": [1] * 4,
            "num_workers": [1] * 4,
        },
        index=pd.Index([1, 2, 3, 4], name="person_id"),
    )
    logsums = simulate.simple_simulate_logsums(
        state,
        people,
        spec,
        nest_spec=None,
        locals_d=settings.CONSTANTS,
        trace_label="school_bus_nan_regression",
        compute_settings=settings.compute_settings,
    )
    # Missing or infinite distance does not satisfy the within-radius term.
    np.testing.assert_allclose(
        logsums, np.logaddexp([0.0, -1.5, 0.0, 0.0], -0.05), rtol=1e-6, atol=1e-6
    )


def test_sampling_exclusions_leave_compiled_choices_enabled():
    from activitysim.core.configuration.base import ComputeSettings

    for name in [
        "school_location",
        "workplace_location",
        "non_mandatory_tour_destination",
        "atwork_subtour_destination",
        "trip_destination",
    ]:
        settings = yaml.safe_load((ROOT / f"model/configs/{name}.yaml").read_text())
        compute = ComputeSettings.model_validate(settings["compute_settings"])
        assert compute.should_skip("sample")
        assert not compute.should_skip("simulate")
        assert not compute.should_skip("logsums")
