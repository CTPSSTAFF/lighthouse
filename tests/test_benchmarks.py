"""Memory qualification must reject invalid evidence and preserve run identity."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_support as support  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "production_benchmark", ROOT / "scripts/production-benchmark.py"
)
bench = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bench
spec.loader.exec_module(bench)


def result(**changes):
    values = dict(
        key="full-p02",
        label="test",
        workers=2,
        household_sample_size=0,
        started_at="",
        duration_seconds=10,
        return_code=0,
        oom_killed=False,
        safety_abort_reason=None,
        container_name="test",
        container_peak_bytes=40 * bench.GIB,
        container_peak_working_set_bytes=39 * bench.GIB,
        container_peak_swap_bytes=0,
        host_min_available_bytes=15 * bench.GIB,
        host_peak_used_bytes=0,
        host_min_macos_free_percent=20,
        output_dir="",
        console_log="",
        cgroup_samples="",
        host_samples="",
        measurement_valid=True,
        output_valid=True,
    )
    values.update(changes)
    return bench.RunResult(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"measurement_valid": False},
        {"output_valid": False},
        {"oom_events": 1},
        {"oom_killed": True},
        {"return_code": 1},
        {"safety_abort_reason": "host pressure"},
        {"container_peak_swap_bytes": 1},
        {"container_peak_bytes": 0},
        {"container_peak_bytes": 49 * bench.GIB},
        {"household_sample_size": 5000},
        {"reused": True},
        {"key": "cache-warmup"},
    ],
)
def test_invalid_runs_do_not_qualify(changes):
    assert not bench.qualifies(result(**changes), 48 * bench.GIB)


def test_valid_full_population_run_qualifies():
    assert bench.qualifies(result(), 48 * bench.GIB)


def test_absent_cgroup_does_not_become_zero(tmp_path):
    with pytest.raises(RuntimeError, match="unavailable"):
        bench.read_cgroup_v2(tmp_path, 0)


def test_cgroup_reads_peak_and_events(tmp_path):
    contents = {
        "cgroup.controllers": "memory",
        "memory.current": "100",
        "memory.peak": "200",
        "memory.max": "300",
        "memory.swap.current": "0",
        "memory.swap.max": "0",
        "memory.stat": "anon 100\n",
        "memory.events": "oom 1\noom_kill 0\n",
    }
    for name, value in contents.items():
        (tmp_path / name).write_text(value)
    sample = bench.read_cgroup_v2(tmp_path, 1)
    assert sample["memory_peak_bytes"] == 200
    assert sample["event_oom"] == 1
    (tmp_path / "memory.peak").write_text("max")
    with pytest.raises(RuntimeError):
        bench.read_cgroup_v2(tmp_path, 1)


def test_sampler_failure_persisted(tmp_path, monkeypatch):
    import threading

    def fail(*args):
        raise RuntimeError("sampling failed")

    monkeypatch.setattr(bench, "_sample_cgroup", fail)
    bench.cgroup_sampler(tmp_path / "samples.csv", 0.01, threading.Event())
    assert json.loads((tmp_path / "samples.error.json").read_text())["error"]


def test_profile_precedence():
    model = ROOT / "model"
    assert support.configs(model, True, "laptop") == (
        model / "configs_explicit_chunk",
        model / "configs_mp",
        model / "configs",
    )
    assert support.configs(model, False, "base") == (model / "configs",)


def test_resume_identity_and_invalidation(tmp_path):
    args = SimpleNamespace(
        sample_interval=1,
        memory_limit="50g",
        qualification_peak="48g",
        shm_size="16g",
        profile="laptop",
        input_identity={"persons.csv": "hash"},
        cache_dir=tmp_path,
    )
    definition = dict(multiprocess=True, workers=2, household_sample_size=0)
    expected = bench.expected_run_spec(definition, "image", "code", args)
    assert expected["allocator_environment"] == bench.ALLOCATOR_ENV
    bench.write_json(tmp_path / "run-spec.json", expected)
    bench.write_json(tmp_path / "run-result.json", bench.asdict(result()))
    assert bench.compatible_completed_result(tmp_path, expected).reused
    for key in [
        "input_identity",
        "model_config_fingerprint",
        "image_id",
        "profile",
        "allocator_environment",
    ]:
        changed = copy.deepcopy(expected)
        changed[key] = "changed"
        assert bench.compatible_completed_result(tmp_path, changed) is None


def test_input_choice_matches_csv_configuration(tmp_path):
    (tmp_path / "persons.csv").touch()
    (tmp_path / "persons.parquet").touch()
    assert support.table_path(tmp_path, "persons").suffix == ".csv"


def test_extensions_register_in_fresh_worker_process(tmp_path):
    import subprocess

    worker = tmp_path / "worker.py"
    worker.write_text(f"""
from pathlib import Path
import sys
sys.path.insert(0, {str(ROOT / "scripts")!r})
import benchmark_support as support
from activitysim import abm
from activitysim.core.workflow import State
state = State.make_default(working_dir=Path({str(ROOT / "model")!r}),
    configs_dir=(Path({str(ROOT / "model/configs")!r}),), output_dir=Path({str(tmp_path)!r}))
support.import_extensions(state, Path({str(ROOT / "model")!r}))
assert state.get('imported_extensions') == ['extensions']
for name in ['constraint_fixed_work_schedule', 'constraint_walk_ability', 'telework_arrangement']:
    assert name in State._RUNNABLE_STEPS
""")
    subprocess.run(
        [sys.executable, str(worker)], check=True, capture_output=True, text=True
    )


def test_preflight_rejects_missing_industry_before_skims(tmp_path):
    import pandas as pd
    import yaml

    model = tmp_path / "model"
    config = model / "configs"
    config.mkdir(parents=True)
    data = tmp_path / "data"
    data.mkdir()
    (config / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "input_table_list": [
                    {
                        "tablename": "persons",
                        "index_col": "person_id",
                        "keep_columns": ["naics_code"],
                    }
                ]
            }
        )
    )
    pd.DataFrame({"person_id": [1]}).to_csv(data / "persons.csv", index=False)
    with pytest.raises(ValueError, match="missing columns.*naics_code"):
        support.preflight(data, model)
