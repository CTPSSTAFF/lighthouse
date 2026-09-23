"""Small synthetic fixtures in ActivitySim's print_run_list/log formats."""

import csv
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

# Import the standalone script without loading unrelated Lighthouse dependencies.
SCRIPT = Path(__file__).resolve().parents[1] / "src/lighthouse/sys_monitor.py"
spec = importlib.util.spec_from_file_location("sys_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = monitor
spec.loader.exec_module(monitor)
FIXTURES = Path(__file__).parent / "fixtures/sys_monitor"


def fixture(name):
    return (FIXTURES / name).read_text()


def tracker(name="run_list.txt"):
    return monitor.StepTracker(monitor.RunPlan.from_text(fixture(name)))


def log(message, logger="mp_tasks"):
    return f"INFO - activitysim.core.{logger} - {message}"


def test_plan_discovers_custom_step_phases_and_worker_counts():
    plan = tracker().plan
    assert plan.models == (
        "initialize_landuse",
        "school_location",
        "constraint_new_access",
        "write_tables",
    )
    assert [p.name for p in plan.phases] == ["prepare", "choices_renamed", "export"]
    assert plan.phases[0].workers == ("prepare",)
    assert plan.phases[1].workers == ("choices_renamed_0", "choices_renamed_1")


def test_staggered_workers_do_not_advance_before_unstarted_worker():
    state = tracker()
    lines = fixture("staggered.log.txt").splitlines()
    for line in lines[:7]:
        state.update(line)
    assert state.current_step_info() == (1, "school_location", "choices_renamed", 1, 2)
    # Repeated messages are idempotent, and the second worker is still required.
    state.update(lines[5])
    assert state.current_step_info()[-2:] == (1, 2)
    state.update(lines[7])
    state.update(lines[8])
    assert state.current_step_info() == (
        2,
        "constraint_new_access",
        "choices_renamed",
        1,
        2,
    )
    state.update(lines[9])
    assert state.current_step_info()[1] == "write_tables"
    for line in lines[10:12]:
        state.update(line)
    assert state.current_step_info()[2] == "FINALIZING"
    assert state.status == "finalizing"
    state.update(lines[12])
    assert state.current_step_info()[2] == "DONE"
    assert state.status == "finished"


def test_unknown_steps_workers_and_unrelated_timings_are_ignored():
    state = tracker()
    for message in (
        "outsider initialize_landuse : 1.0 seconds",
        "prepare nonexistent : 1.0 seconds",
        "prepare initialize_landuse UNTIL ERROR : 1.0 seconds",
    ):
        state.update(log(message))
    state.update(log("prepare initialize_landuse : 1.0 seconds", "tracing"))
    assert state.current_step_info() == (0, "initialize_landuse", "prepare", 0, 1)


def test_renamed_one_worker_phase_and_phase_scoping():
    state = tracker()
    state.update(log("choices_renamed_0 initialize_landuse : 1.0 seconds"))
    assert state.current_step_info()[0] == 0
    state.update(log("prepare initialize_landuse : 1.0 seconds"))
    assert state.current_step_info()[0] == 1


def test_latest_resume_seeds_only_saved_success_and_waits_for_remaining_worker():
    state = tracker("resume_latest.txt")
    assert state.current_step_info() == (1, "school_location", "choices_renamed", 1, 2)
    for line in fixture("resumed.log.txt").splitlines()[:3]:
        state.update(line)
    assert state.current_step_info() == (3, "write_tables", "export", 0, 1)


def test_named_resume_does_not_reuse_old_completed_worker_list():
    state = tracker("resume_named.txt")
    assert state.current_step_info() == (1, "school_location", "choices_renamed", 0, 2)
    assert state.status == "resuming"
    state.update(log("choices_renamed_0 constraint_new_access : 0.02 seconds"))
    assert state.current_step_info()[-2:] == (1, 2)
    state.update(log("choices_renamed_1 constraint_new_access : 0.02 seconds"))
    assert state.current_step_info()[1] == "write_tables"


def test_resumed_worker_can_restore_entire_phase_without_model_completion_lines():
    state = tracker("resume_latest.txt")
    state.update(log("process choices_renamed_1 completed"))
    assert state.current_step_info()[1] == "write_tables"


def test_resume_request_without_breadcrumbs_does_not_skip_work():
    text = fixture("run_list.txt").replace("resume_after: None", "resume_after: _")
    state = monitor.StepTracker(monitor.RunPlan.from_text(text))
    assert state.current_step_info()[0] == 0


@pytest.mark.parametrize("logger", ["workflow.runner", "pipeline"])
def test_single_process_resume_and_completion(logger):
    state = tracker("single_process.txt")
    lines = (
        fixture("single_process.log.txt")
        .replace("workflow.runner", logger)
        .splitlines()
    )
    state.update(lines[0])
    assert state.current_step_info() == (
        1,
        "constraint_new_access",
        "single_process",
        0,
        1,
    )
    for line in lines[1:-1]:
        state.update(line)
    assert state.status == "finalizing"
    state.update(lines[-1])
    assert state.status == "finished"


def test_failure_is_not_overridden_by_late_completion_or_exit():
    state = tracker()
    state.update(log("process choices_renamed_1 failed with exitcode -9"))
    state.update(log("Time to execute all models : 10.0 seconds", "tracing"))
    assert state.status == "failed"
    assert state.current_step_info()[2] != "DONE"


def test_coalesce_failure_after_model_steps_complete():
    state = tracker()
    for line in fixture("staggered.log.txt").splitlines()[:-1]:
        state.update(line)
    state.update(
        log("Time to execute all models until this error : 10.0 seconds", "tracing")
    )
    assert state.status == "failed"


@pytest.mark.parametrize(
    "old,new",
    [
        ("multiprocess: True", "multiprocess: maybe"),
        ("num_processes: 2", "num_processes: 0"),
        ("num_processes: 2", "num_processes: many"),
        ("       - constraint_new_access\n", ""),
        ("  - school_location\n", "  - initialize_landuse\n"),
        ("name: export", "name: inconsistent"),
    ],
)
def test_malformed_or_partial_plan_is_rejected(old, new):
    with pytest.raises(ValueError):
        monitor.RunPlan.from_text(fixture("run_list.txt").replace(old, new))


def test_unknown_resume_worker_is_rejected():
    with pytest.raises(ValueError, match="worker"):
        monitor.RunPlan.from_text(
            fixture("resume_latest.txt").replace(
                "['choices_renamed_0']", "['unknown_0']"
            )
        )


def test_reordered_breadcrumbs_are_rejected():
    with pytest.raises(ValueError, match="breadcrumbs"):
        monitor.RunPlan.from_text(
            fixture("resume_latest.txt").replace(
                "breadcrumbs:\n  step: prepare", "breadcrumbs:\n  step: export"
            )
        )


def test_late_attachment_replays_more_than_tail_window(tmp_path):
    (tmp_path / "run_list.txt").write_text(fixture("run_list.txt"))
    path = tmp_path / "activitysim.log"
    lines = fixture("staggered.log.txt").splitlines(keepends=True)
    # Important early completions are far outside the old tail window.
    path.write_text(
        "".join(lines[:10]) + "irrelevant detail\n" * 20000 + "".join(lines[10:])
    )
    progress = monitor.RunMonitor(path, chunk_bytes=17)
    progress.poll()
    assert progress.warning is None
    assert progress.tracker.status == "finished"
    offset = progress.reader.offset
    progress.poll()
    assert progress.reader.offset == offset
    assert progress.tracker.status == "finished"


def test_partial_line_is_preserved_until_complete(tmp_path):
    path = tmp_path / "activitysim.log"
    path.write_bytes(b"first\npar")
    reader = monitor.LogReader(path, chunk_bytes=2)
    assert list(reader.lines(lambda: pytest.fail("unexpected reset"))) == ["first"]
    with path.open("ab") as stream:
        stream.write("tial café\n".encode())
    assert list(reader.lines(lambda: pytest.fail("unexpected reset"))) == [
        "partial café"
    ]


@pytest.mark.parametrize("replace", [False, True])
def test_log_truncation_or_replacement_discards_completion(tmp_path, replace):
    (tmp_path / "run_list.txt").write_text(fixture("run_list.txt"))
    path = tmp_path / "activitysim.log"
    path.write_text(fixture("staggered.log.txt"))
    progress = monitor.RunMonitor(path)
    progress.poll()
    assert progress.tracker.status == "finished"
    if replace:
        path.rename(tmp_path / "old.log")
    # Regrow beyond the old size, exercising the boundary check too.
    path.write_text("new run starting\n" * 1000)
    progress.poll()
    assert progress.tracker.current_step_info()[0] == 0
    assert progress.tracker.status == "waiting"


def test_missing_then_partial_then_valid_plan_replays_existing_log(tmp_path):
    path = tmp_path / "activitysim.log"
    path.write_text(fixture("staggered.log.txt"))
    progress = monitor.RunMonitor(path)
    progress.poll()
    assert progress.tracker is None
    assert "Progress unavailable" in progress.warning
    plan = tmp_path / "run_list.txt"
    plan.write_text("resume_after: None\nmultiprocess: True\nmodels:\n")
    progress.poll()
    assert progress.tracker is None
    plan.write_text(fixture("run_list.txt"))
    progress.poll()
    assert progress.tracker.status == "finished"
    assert progress.warning is None


def test_explicit_plan_path_and_changed_plan(tmp_path):
    plan = tmp_path / "custom_plan.txt"
    plan.write_text(fixture("run_list.txt"))
    path = tmp_path / "activitysim.log"
    path.write_text("")
    progress = monitor.RunMonitor(path, plan)
    progress.poll()
    assert progress.tracker.current_step_info()[0] == 0
    plan.write_text(fixture("resume_latest.txt"))
    progress.poll()
    assert progress.tracker.current_step_info()[0] == 1


def test_missing_log_never_claims_running_or_done(tmp_path):
    (tmp_path / "run_list.txt").write_text(fixture("run_list.txt"))
    progress = monitor.RunMonitor(tmp_path / "missing.log")
    progress.poll()
    assert progress.tracker is None
    assert progress.warning


def test_cli_csv_and_parent_exit_do_not_claim_success(tmp_path, monkeypatch, capsys):
    path = tmp_path / "activitysim.log"
    path.write_text(fixture("staggered.log.txt").splitlines()[0] + "\n")
    (tmp_path / "run_list.txt").write_text(fixture("run_list.txt"))
    csv_path = tmp_path / "usage.csv"
    monkeypatch.setattr(monitor.psutil, "cpu_percent", lambda **kwargs: 12.5)
    monkeypatch.setattr(
        monitor.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=2048, available=1024),
    )
    monkeypatch.setattr(
        monitor.psutil,
        "Process",
        lambda pid: SimpleNamespace(name=lambda: "model", is_running=lambda: False),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--log",
            str(path),
            "--csv",
            str(csv_path),
            "--parent-pid",
            "123",
            "--tail-bytes",
            "8",
        ],
    )
    monitor.main()
    with csv_path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["step_name"] == "initialize_landuse"
    assert rows[0]["status"] == "running"
    assert rows[0]["workers_total"] == "1"
    assert "Stopping monitor (running)" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_invalid_interval(value):
    with pytest.raises(monitor.argparse.ArgumentTypeError):
        monitor.positive_float(value)


def test_fresh_single_process_does_not_skip_missing_completions():
    plan = monitor.RunPlan.from_text(
        fixture("single_process.txt").replace("resume_after: _", "resume_after: None")
    )
    state = monitor.StepTracker(plan)
    state.update(
        log(
            "time to execute run.constraint_new_access : 1.0 seconds", "workflow.runner"
        )
    )
    assert state.current_step_info()[1] == "initialize_landuse"
    state.update(
        log("time to execute run.initialize_landuse : 1.0 seconds", "workflow.runner")
    )
    assert state.current_step_info()[1] == "write_tables"


def test_named_resume_can_rerun_checkpoint_instead_of_restoring_it():
    state = tracker("resume_named.txt")
    state.update(log("choices_renamed_0 school_location : 0.02 seconds"))
    assert state.current_step_info()[1] == "school_location"
    assert state.current_step_info()[-2:] == (1, 2)
    assert state.status == "resuming"
    state.update(log("choices_renamed_1 school_location : 0.02 seconds"))
    assert state.current_step_info()[1] == "constraint_new_access"
    assert state.status == "running"


def test_appended_log_advances_without_replaying_existing_history(tmp_path):
    (tmp_path / "run_list.txt").write_text(fixture("run_list.txt"))
    path = tmp_path / "activitysim.log"
    lines = fixture("staggered.log.txt").splitlines(keepends=True)
    path.write_text("".join(lines[:7]))
    progress = monitor.RunMonitor(path, chunk_bytes=31)
    progress.poll()
    assert progress.tracker.current_step_info()[-2:] == (1, 2)
    state = progress.tracker
    with path.open("a") as stream:
        stream.writelines(lines[7:])
    progress.poll()
    assert progress.tracker is state
    assert state.status == "finished"


def test_resource_csv_continues_with_missing_plan_and_appends_one_header(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(monitor.psutil, "cpu_percent", lambda **kwargs: 25.0)
    monkeypatch.setattr(
        monitor.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=2048, available=1024),
    )
    monkeypatch.setattr(
        monitor.psutil,
        "Process",
        lambda pid: SimpleNamespace(name=lambda: "model", is_running=lambda: False),
    )
    path = tmp_path / "usage.csv"
    for _ in range(2):
        monitor.monitor(
            csv_path=path, log_path=tmp_path / "missing.log", parent_pid=123
        )
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert all(
        row["status"] == "unknown"
        and row["step_name"] == ""
        and row["workers_total"] == ""
        and row["cpu_percent"] == "25.0"
        for row in rows
    )


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_invalid_log_chunk_size(value):
    with pytest.raises(monitor.argparse.ArgumentTypeError):
        monitor.positive_int(value)
