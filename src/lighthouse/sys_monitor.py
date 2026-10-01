#!/usr/bin/env python3
"""Sample CPU/memory and track an ActivitySim run using its resolved run_list.txt.

The run-list adapter is deliberately separate from execution tracking: ActivitySim's
informational text format is not YAML or a versioned public interchange format.
"""

import argparse
import ast
import csv
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import sys
import time
from typing import Optional

try:
    import psutil
except ImportError:
    print(
        "ERROR: 'psutil' is not installed. Install it with: python -m pip install psutil",
        file=sys.stderr,
    )
    sys.exit(1)


@dataclass(frozen=True)
class Phase:
    name: str
    models: tuple[str, ...]
    workers: tuple[str, ...]
    resume_after: Optional[str] = None
    completed_workers: tuple[str, ...] = ()
    simulated: bool = False


@dataclass(frozen=True)
class RunPlan:
    models: tuple[str, ...]
    phases: tuple[Phase, ...]
    multiprocess: bool
    resume_after: Optional[str]

    @classmethod
    def from_text(cls, text: str) -> "RunPlan":
        """Read the narrow print_run_list format, rejecting incomplete/ambiguous plans.

        In particular, repeated ``step:`` blocks must not be loaded as a YAML
        mapping (which could silently discard all but the last phase).
        Ignore unrelated fields, but validate every field used for progress.
        """
        headers = {}
        models = []
        phases = []
        breadcrumbs = {}
        section = None
        block = None
        in_models = False
        for line in text.splitlines():
            value = line.strip()
            if not value:
                continue
            if not line.startswith(" "):
                in_models = False
                if value in ("models:", "multiprocess_steps:", "breadcrumbs:"):
                    section = value[:-1]
                    block = None
                elif ":" in value:
                    key, val = value.split(":", 1)
                    headers[key] = val.strip()
                    section = None
                continue
            if section == "models":
                if not value.startswith("- "):
                    raise ValueError("Invalid models list in run_list.txt")
                models.append(value[2:].strip())
            elif section in ("multiprocess_steps", "breadcrumbs"):
                if line.startswith("  step: "):
                    name = value.split(":", 1)[1].strip()
                    block = {"name": name, "models": []}
                    in_models = False
                    if section == "multiprocess_steps":
                        phases.append(block)
                    else:
                        if name in breadcrumbs:
                            raise ValueError("Duplicate breadcrumb phase")
                        breadcrumbs[name] = block
                elif block is not None:
                    if section == "multiprocess_steps":
                        if value == "models:":
                            in_models = True
                        elif in_models and value.startswith("- "):
                            block["models"].append(value[2:].strip())
                        else:
                            in_models = False
                            key, sep, val = value.partition(":")
                            if sep and key in ("num_processes", "resume_after", "name"):
                                if key == "name" and val.strip() != block["name"]:
                                    raise ValueError("Inconsistent phase name")
                                block[key] = val.strip()
                    else:
                        # print_run_list prints breadcrumb fields WITHOUT colons.
                        key, _, val = value.partition(" ")
                        if key in ("simulate", "completed"):
                            try:
                                block[key] = ast.literal_eval(val.strip())
                            except (ValueError, SyntaxError) as exc:
                                raise ValueError("Invalid resume breadcrumbs") from exc
        if (
            headers.get("multiprocess") not in ("True", "False")
            or "resume_after" not in headers
        ):
            raise ValueError(
                "Missing multiprocess/resume_after headers in run_list.txt"
            )
        if not models or any(not m for m in models) or len(set(models)) != len(models):
            raise ValueError("Expected a nonempty, unique model sequence")
        resume = headers["resume_after"]
        resume = None if resume == "None" else resume
        if resume not in (None, "_") and resume not in models:
            raise ValueError("Resume checkpoint is not in the model sequence")
        multiprocess = headers["multiprocess"] == "True"
        if not multiprocess:
            if phases or breadcrumbs:
                raise ValueError("Unexpected phases in a single-process plan")
            return cls(
                tuple(models),
                (Phase("single_process", tuple(models), ("MainProcess",), resume),),
                False,
                resume,
            )
        if not phases or [m for p in phases for m in p["models"]] != models:
            raise ValueError("Phase model lists do not match the full model sequence")
        names = [p["name"] for p in phases]
        if len(set(names)) != len(names) or any(not n for n in names):
            raise ValueError("Phase names must be nonempty and unique")
        if list(breadcrumbs) != names[: len(breadcrumbs)]:
            raise ValueError("Resume breadcrumbs do not match the phase sequence")
        result = []
        for p in phases:
            try:
                count = int(p.get("num_processes", ""))
            except ValueError as exc:
                raise ValueError("Missing/invalid resolved num_processes") from exc
            if count < 1 or not p["models"]:
                raise ValueError("Each phase needs models and a positive worker count")
            workers = (
                (p["name"],)
                if count == 1
                else tuple(f"{p['name']}_{i}" for i in range(count))
            )
            checkpoint = p.get("resume_after")
            checkpoint = None if checkpoint == "None" else checkpoint
            if checkpoint not in (None, "_") and checkpoint not in p["models"]:
                raise ValueError("Phase resume checkpoint is not in that phase")
            crumb = breadcrumbs.get(p["name"], {}) if resume else {}
            completed = crumb.get("completed", [])
            if not isinstance(completed, list) or any(
                not isinstance(w, str) or w not in workers for w in completed
            ):
                raise ValueError("Invalid completed worker list")
            simulated = crumb.get("simulate")
            if simulated is not None and not isinstance(simulated, bool):
                raise ValueError("Invalid simulate breadcrumb")
            # A named checkpoint reruns workers even if they previously completed.
            result.append(
                Phase(
                    p["name"],
                    tuple(p["models"]),
                    workers,
                    checkpoint,
                    tuple(completed) if checkpoint == "_" else (),
                    simulated is True,
                )
            )
        all_workers = [w for p in result for w in p.workers]
        if len(set(all_workers)) != len(all_workers):
            raise ValueError("Ambiguous worker names across phases")
        return cls(tuple(models), tuple(result), True, resume)


# Match logger and message structure, never a fixed vocabulary of model/phase names.
LOG_MESSAGE = re.compile(
    r"\b(activitysim\.core\.[\w.]+|activitysim\.cli\.run)\s*-\s*(.*)"
)
DURATION = r"[\d.]+\s+seconds\b"
COMPLETED = re.compile(rf"(\S+)\s+(\S+)\s*:\s*{DURATION}")
PROCESS_DONE = re.compile(
    r"process (\S+) completed(?: with exitcode 0)?$", re.IGNORECASE
)
PROCESS_FAILED = re.compile(r"process (\S+) failed with exitcode", re.IGNORECASE)
SINGLE_DONE = re.compile(rf"time to execute run\.(\S+)\s*:\s*{DURATION}", re.IGNORECASE)
RUN_DONE = re.compile(
    rf"Time to execute all models(?: completed)?\s*:\s*{DURATION}", re.IGNORECASE
)


class StepTracker:
    """Report the earliest step not satisfied by every planned worker.

    In resumed phases a worker completing a later step proves that its earlier
    steps were run or restored. A request to resume alone does not prove that.
    """

    def __init__(self, plan: RunPlan):
        self.plan = plan
        self.phase_by_worker = {w: p for p in plan.phases for w in p.workers}
        self.phase_by_model = {m: p for p in plan.phases for m in p.models}
        self.reset()

    def reset(self) -> None:
        self.completed = {m: set() for m in self.plan.models}
        self.resume_pending = {
            w
            for phase in self.plan.phases
            if phase.resume_after and not phase.simulated
            for w in phase.workers
            if w not in phase.completed_workers
        }
        self.observed = False
        self.failed = False
        self.finished = False
        for phase in self.plan.phases:
            for model in phase.models:
                self.completed[model].update(
                    phase.workers if phase.simulated else phase.completed_workers
                )

    def complete(self, worker: str, model: str) -> None:
        phase = self.phase_by_worker.get(worker)
        if phase is None or model not in phase.models:
            return
        self.observed = True
        self.resume_pending.discard(worker)
        models = (
            phase.models[: phase.models.index(model) + 1]
            if phase.resume_after
            else (model,)
        )
        for name in models:
            self.completed[name].add(worker)

    def update(self, line: str) -> None:
        match = LOG_MESSAGE.search(line)
        if not match:
            return
        logger, msg = match.groups()
        # Overall success is separate from model completion (coalescing may fail).
        if logger in (
            "activitysim.core.tracing",
            "activitysim.core.workflow.runner",
            "activitysim.cli.run",
        ):
            if RUN_DONE.match(msg):
                self.finished = not self.failed
                self.observed = True
            if (
                "activitysim run encountered an unrecoverable error" in msg
                or "all models until this error" in msg
            ):
                self.failed = True
                self.finished = False
        if logger == "activitysim.core.mp_tasks" and self.plan.multiprocess:
            match = COMPLETED.fullmatch(msg.split(" (", 1)[0])
            if match:
                self.complete(*match.groups())
            match = PROCESS_DONE.fullmatch(msg)
            if match and match[1] in self.phase_by_worker:
                phase = self.phase_by_worker[match[1]]
                for model in phase.models:
                    self.complete(match[1], model)
            if PROCESS_FAILED.match(msg):
                self.failed = True
                self.finished = False
            if msg.startswith(("start process ", "run_sub_simulations step ")):
                self.observed = True
        elif not self.plan.multiprocess and logger in (
            "activitysim.core.pipeline",
            "activitysim.core.workflow.runner",
        ):
            match = SINGLE_DONE.match(msg)
            if match:
                self.complete("MainProcess", match[1])
            if msg.startswith("resume_after "):
                checkpoint = msg.removeprefix("resume_after ")
                if checkpoint in self.plan.models:
                    self.observed = True
                    self.resume_pending.discard("MainProcess")
                    for model in self.plan.models[
                        : self.plan.models.index(checkpoint) + 1
                    ]:
                        self.completed[model].add("MainProcess")
            if "#run_model running step " in msg:
                self.observed = True

    def current_step_info(
        self,
    ) -> tuple[Optional[int], Optional[str], str, Optional[int], Optional[int]]:
        """Return zero-based index, model, phase, satisfied workers, expected workers."""
        if self.finished:
            return None, None, "DONE", None, None
        for idx, model in enumerate(self.plan.models):
            phase = self.phase_by_model[model]
            done = len(self.completed[model])
            if done < len(phase.workers):
                return idx, model, phase.name, done, len(phase.workers)
        return None, None, "FINALIZING", None, None

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        if self.finished:
            return "finished"
        idx, model, _, _, _ = self.current_step_info()
        if idx is None:
            return "finalizing"
        phase = self.phase_by_model[model]
        if self.resume_pending.intersection(phase.workers):
            return "resuming"
        return "running" if self.observed else "waiting"


class LogReader:
    """Replay once, then read appended complete lines in bounded chunks.

    Retain partial lines across ticks. Detect replacement/truncation, including
    truncate-and-regrow when the previously read boundary has changed.
    """

    def __init__(self, path: Path, chunk_bytes: int = 256 * 1024):
        if chunk_bytes <= 0:
            raise ValueError("Log read chunk size must be positive")
        self.path = Path(path)
        self.chunk_bytes = chunk_bytes
        self.reset()

    def reset(self):
        self.identity = None
        self.offset = 0
        self.pending = b""
        self.boundary = b""

    def lines(self, on_reset):
        with self.path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            identity = (stat.st_dev, stat.st_ino)
            stream.seek(max(0, self.offset - len(self.boundary)))
            boundary = stream.read(len(self.boundary))
            if self.identity is not None and (
                identity != self.identity
                or stat.st_size < self.offset
                or boundary != self.boundary
            ):
                self.reset()
                on_reset()
            self.identity = identity
            stream.seek(self.offset)
            # Only consume the snapshot available at the start of this poll.
            remaining = stat.st_size - self.offset
            while remaining > 0:
                chunk = stream.read(min(self.chunk_bytes, remaining))
                if not chunk:
                    break
                self.offset += len(chunk)
                remaining -= len(chunk)
                self.boundary = (self.boundary + chunk)[-128:]
                parts = (self.pending + chunk).split(b"\n")
                self.pending = parts.pop()
                for line in parts:
                    yield line.decode("utf-8", errors="replace").rstrip("\r")


class RunMonitor:
    """Reload changed plans and replay logs so late plan creation loses no events."""

    def __init__(self, log_path, run_list_path=None, chunk_bytes=256 * 1024):
        self.reader = LogReader(Path(log_path), chunk_bytes)
        self.plan_path = (
            Path(run_list_path)
            if run_list_path
            else Path(log_path).with_name("run_list.txt")
        )
        self.plan_stamp = None
        self.tracker = None
        self.warning = None

    def poll(self) -> None:
        try:
            stat = self.plan_path.stat()
            stamp = (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size)
            if stamp != self.plan_stamp:
                plan = RunPlan.from_text(self.plan_path.read_text(encoding="utf-8"))
                self.tracker = StepTracker(plan)
                self.plan_stamp = stamp
                self.reader.reset()
            for line in self.reader.lines(self.tracker.reset):
                self.tracker.update(line)
            self.warning = None
        except (OSError, ValueError) as exc:
            self.warning = f"Progress unavailable: {exc}. Waiting for readable, valid run_list.txt and log files."
            # Never retain DONE or guessed progress while an artifact is invalid.
            self.tracker = None
            self.plan_stamp = None


def format_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def bytes_to_gb(n_bytes: int) -> float:
    return n_bytes / (1024**3)


def monitor(
    interval=0.5,
    csv_path=None,
    log_path=None,
    tail_bytes=256 * 1024,
    parent_pid=None,
    delay_seconds=0,
    run_list_path=None,
):
    """Sample resources; --tail-bytes now controls read chunks, not retained history."""
    if delay_seconds > 0:
        print(f"Delaying sys_monitor start for {delay_seconds} seconds...")
        time.sleep(delay_seconds)
    psutil.cpu_percent(interval=None)
    progress = RunMonitor(log_path, run_list_path, tail_bytes) if log_path else None
    parent = None
    if parent_pid is not None:
        try:
            parent = psutil.Process(parent_pid)
            print(f"Monitoring parent process PID {parent_pid} ({parent.name()})")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            print(f"Warning: Cannot access parent process {parent_pid}: {exc}")
    csv_file = None
    previous_warning = None
    try:
        if csv_path:
            has_content = Path(csv_path).exists() and Path(csv_path).stat().st_size > 0
            csv_file = open(csv_path, "a", encoding="utf-8", newline="")
            writer = csv.writer(csv_file)
            if not has_content:
                writer.writerow(
                    [
                        "timestamp",
                        "cpu_percent",
                        "memory_used_gb",
                        "memory_available_gb",
                        "available_memory_pct",
                        "phase",
                        "step_index",
                        "step_name",
                        "status",
                        "workers_done",
                        "workers_total",
                    ]
                )
        print("Press Ctrl+C to stop.")
        while True:
            ts = format_now()
            cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            used_gb = bytes_to_gb(vm.total - vm.available)
            avail_gb = bytes_to_gb(vm.available)
            avail_pct = vm.available / vm.total * 100 if vm.total else 0.0
            tracker = None
            if progress:
                progress.poll()
                if progress.warning and progress.warning != previous_warning:
                    print(progress.warning)
                previous_warning = progress.warning
                tracker = progress.tracker
            idx, step, phase, done, total = (
                tracker.current_step_info()
                if tracker
                else (None, None, "UNKNOWN", None, None)
            )
            status = tracker.status if tracker else "unknown"
            count = len(tracker.plan.models) if tracker else None
            step_progress = (
                f"{idx + 1 if idx is not None else count}/{count}" if tracker else "?/?"
            )
            workers = f" (workers: {done}/{total})" if total is not None else ""
            print(
                f"{ts} | CPU: {cpu:5.1f}% | Used: {used_gb:6.2f} GB | "
                f"Available: {avail_gb:6.2f} GB ({avail_pct:5.1f}%) | "
                f"Phase: {phase} | Step: {step_progress} | "
                f"{step or phase}{workers} ({status})"
            )
            if csv_file:
                writer.writerow(
                    [
                        ts,
                        f"{cpu:.1f}",
                        f"{used_gb:.2f}",
                        f"{avail_gb:.2f}",
                        f"{avail_pct:.1f}",
                        phase,
                        idx + 1 if idx is not None else "",
                        step or "",
                        status,
                        done if done is not None else "",
                        total if total is not None else "",
                    ]
                )
                csv_file.flush()
            # Consume final log records before stopping; exit never implies success.
            if parent is not None:
                try:
                    if not parent.is_running():
                        print(
                            f"Parent process {parent_pid} has exited. Stopping monitor ({status})."
                        )
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    print(
                        f"Parent process {parent_pid} is unavailable. Stopping monitor ({status})."
                    )
                    break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        if csv_file:
            csv_file.close()


def positive_float(value):
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Value must be a number") from exc
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("Value must be finite and > 0")
    return number


def positive_int(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Value must be an integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be > 0")
    return number


def main():
    parser = argparse.ArgumentParser(
        description="Track CPU/memory and ActivitySim progress from the resolved run plan and log."
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=positive_float,
        default=0.5,
        help="Sampling interval in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--csv", default="../output/log/sys_usage.csv", help="CSV output path"
    )
    parser.add_argument(
        "--log",
        default="../output/log/activitysim.log",
        help="ActivitySim main log path",
    )
    parser.add_argument(
        "--run-list", help="Resolved run_list.txt path (default: alongside --log)"
    )
    parser.add_argument(
        "--tail-bytes",
        type=positive_int,
        default=256 * 1024,
        help="Read chunk size in bytes (default: 262144); all existing log history is replayed",
    )
    parser.add_argument("--parent-pid", type=int, help="Stop when this process exits")
    parser.add_argument(
        "--delay",
        type=positive_float,
        default=0,
        help="Delay before monitoring, in seconds",
    )
    args = parser.parse_args()
    monitor(
        interval=args.interval,
        csv_path=args.csv,
        log_path=args.log,
        tail_bytes=args.tail_bytes,
        parent_pid=args.parent_pid,
        delay_seconds=args.delay,
        run_list_path=args.run_list,
    )


if __name__ == "__main__":
    main()
