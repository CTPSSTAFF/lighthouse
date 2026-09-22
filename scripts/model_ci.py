"""Run the locked model against frozen household IDs and validate its outputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import psutil
import yaml

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_population(households, persons):
    for name, frame in [("households", households), ("persons", persons)]:
        require(
            frame.index.is_unique and not frame.index.hasnans, f"{name}: invalid IDs"
        )
    require(
        persons.household_id.isin(households.index).all(), "persons: unknown household"
    )
    sizes = (
        persons.groupby("household_id").size().reindex(households.index, fill_value=0)
    )
    require(
        sizes.eq(households.hhsize).all(),
        "households: hhsize differs from person count",
    )
    require(persons.age.between(0, 120).all(), "persons: invalid age")
    require(
        persons.pemploy.isin([1, 2, 3, 4]).all(), "persons: invalid employment type"
    )


def validate_outputs(inputs, tables, zones):
    h, p = tables["households"], tables["persons"]
    validate_population(h, p)
    for name in ["households", "persons"]:
        require(
            set(tables[name].index) == set(inputs[name].index),
            f"{name}: population changed",
        )
    require(
        p.household_id.equals(inputs["persons"].household_id.reindex(p.index)),
        "persons: household assignment changed",
    )
    for name in ["tours", "trips"]:
        frame = tables[name]
        require(len(frame) > 0, f"{name}: empty output")
        require(
            frame.index.is_unique and not frame.index.hasnans, f"{name}: invalid IDs"
        )
        require(frame.person_id.isin(p.index).all(), f"{name}: unknown person")
        require(
            frame.household_id.eq(
                p.household_id.reindex(frame.person_id).to_numpy()
            ).all(),
            f"{name}: inconsistent household",
        )
        for col in ["origin", "destination"]:
            require(frame[col].isin(zones).all(), f"{name}: invalid {col}")
        mode = "tour_mode" if name == "tours" else "trip_mode"
        require(
            frame[mode].notna().all() and frame[mode].astype(str).ne("").all(),
            f"{name}: missing mode",
        )
    tours, trips = tables["tours"], tables["trips"]
    require(trips.tour_id.isin(tours.index).all(), "trips: unknown tour")
    require(
        trips.person_id.eq(tours.person_id.reindex(trips.tour_id).to_numpy()).all(),
        "trips: inconsistent tour owner",
    )
    require(set(trips.tour_id) == set(tours.index), "tours: missing trips")
    require(
        tours.start.between(1, 24).all()
        and tours.end.between(1, 24).all()
        and tours.start.le(tours.end).all(),
        "tours: invalid times",
    )
    require(trips.depart.between(1, 24).all(), "trips: invalid departure")
    require(trips.outbound.isin([True, False]).all(), "trips: invalid direction")
    for (_, _), group in trips.groupby(["tour_id", "outbound"]):
        group = group.sort_values("trip_num")
        require(
            group.trip_num.tolist() == list(range(1, len(group) + 1)),
            "trips: broken sequence",
        )
        require(group.trip_count.eq(len(group)).all(), "trips: incorrect trip_count")
        require(group.depart.is_monotonic_increasing, "trips: departure order")
        require(
            np.array_equal(
                group.destination.to_numpy()[:-1], group.origin.to_numpy()[1:]
            ),
            "trips: disconnected path",
        )
    for col in ["can_travel_alone", "school_bus_available"]:
        if col in p:
            require(
                p[col].notna().all() and p[col].isin([True, False]).all(),
                f"{col}: invalid result",
            )


def distributions(tables):
    result = {"counts": {name: len(frame) for name, frame in tables.items()}}
    for table, col in [
        ("persons", "cdap_activity"),
        ("households", "auto_ownership"),
        ("tours", "tour_type"),
        ("tours", "tour_mode"),
        ("trips", "trip_mode"),
    ]:
        result[f"{table}.{col}"] = {
            str(k): float(v)
            for k, v in tables[table][col]
            .value_counts(normalize=True)
            .sort_index()
            .items()
        }
    return result


def advisory(current, baseline):
    lines = [
        "## Model distributions (advisory)",
        "",
        "| Metric | Baseline | Current | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric in sorted(set(current) | set(baseline)):
        for key in sorted(set(current.get(metric, {})) | set(baseline.get(metric, {}))):
            old = baseline.get(metric, {}).get(key, 0)
            new = current.get(metric, {}).get(key, 0)
            if metric == "counts":
                lines.append(f"| {metric}.{key} | {old} | {new} | {new - old:+} |")
            else:
                lines.append(
                    f"| {metric}.{key} | {old:.2%} | {new:.2%} | {(new - old) * 100:+.2f} pp |"
                )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--households", type=int, default=2000)
    parser.add_argument("--output", type=Path, default=ROOT / "model/output_ci")
    parser.add_argument("--single-process", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    require(not output.exists(), f"Refusing to reuse existing output: {output}")
    output.mkdir(parents=True)
    data = output / "inputs"
    data.mkdir()
    report_dir = output / "report"
    report_dir.mkdir()
    source = ROOT / "model/data"
    ids = json.loads((ROOT / "tests/fixtures/household_ids.json").read_text())[
        "household_ids"
    ]
    require(0 < args.households <= len(ids), "Unsupported household sample size")
    ids = ids[: args.households]
    households = (
        pd.read_csv(source / "households.csv", index_col="household_id")
        .loc[ids]
        .sort_index()
    )
    persons = pd.read_csv(source / "persons.csv", index_col="person_id")
    persons = persons.loc[persons.household_id.isin(ids)].sort_index()
    validate_population(households, persons)
    require(set(persons.pemploy) == {1, 2, 3, 4}, "Fixture lacks employment coverage")
    require(
        {1, 2}.issubset(set(persons.pstudent)),
        "Fixture lacks school/university students",
    )
    inputs = {"households": households, "persons": persons}
    for name, frame in inputs.items():
        frame.to_csv(data / f"{name}.csv")
    configs = [ROOT / "tests/model", ROOT / "model/configs_mp", ROOT / "model/configs"]
    if args.single_process:
        overlay = output / "config"
        overlay.mkdir()
        (overlay / "settings.yaml").write_text(
            "inherit_settings: true\nmultiprocess: false\n"
        )
        configs.insert(0, overlay)
    command = [sys.executable, "-m", "activitysim", "run"]
    for config in configs:
        command += ["-c", str(config)]
    command += ["-d", str(data), "-d", str(source), "-o", str(output)]
    if (ROOT / "extensions").is_dir():
        command += ["--ext", str(ROOT / "extensions")]
    env = os.environ.copy()
    for name in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMBA_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ]:
        env[name] = "1"
    tracked_inputs = list(source.glob("*.csv")) + list(source.glob("*.omx"))
    tracked_configs = list((ROOT / "model/configs").glob("*")) + list(
        (ROOT / "model/configs_mp").glob("*")
    )
    metadata = {
        "seed": 0,
        "sample_households": args.households,
        "single_process": args.single_process,
        "python": sys.version,
        "platform": platform.platform(),
        "command": command,
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "packages": {
            p: importlib.metadata.version(p)
            for p in ["activitysim", "sharrow", "numpy", "pandas"]
        },
        "sha256": {
            str(p.relative_to(ROOT)): digest(p)
            for p in tracked_inputs
            + tracked_configs
            + [
                ROOT / "uv.lock",
                ROOT / "tests/model/settings.yaml",
                ROOT / "tests/fixtures/household_ids.json",
            ]
            if p.is_file()
        },
    }
    started = time.monotonic()
    peak = 0
    with (report_dir / "console.log").open("w") as log:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
        )
        while process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                rss = 0
                for item in [parent, *parent.children(recursive=True)]:
                    try:
                        rss += item.memory_info().rss
                    except (psutil.Error, OSError):
                        pass
                peak = max(peak, rss)
            except (psutil.Error, OSError):
                pass
            time.sleep(0.5)
    metadata.update(
        returncode=process.returncode,
        seconds=time.monotonic() - started,
        peak_summed_rss_bytes=peak,
    )
    (report_dir / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    text = (report_dir / "console.log").read_text()
    warnings = [
        line for line in text.splitlines() if "WARNING" in line or "ERROR" in line
    ]
    (report_dir / "warnings.log").write_text("\n".join(warnings) + "\n")
    try:
        require(
            process.returncode == 0,
            f"Model exited {process.returncode}; see {report_dir}/console.log",
        )
        tables = {
            name: pd.read_parquet(output / f"final_{name}.parquet")
            for name in ["households", "persons", "tours", "trips"]
        }
        zones = pd.read_csv(source / "land_use.csv").TAZ
        validate_outputs(inputs, tables, zones)
        expected = yaml.safe_load(
            (ROOT / "model/configs_mp/settings.yaml").read_text()
        )["models"]
        # Each component reports its successful completion; write_tables is logged after its checkpoint export.
        for step in expected:
            require(
                re.search(r"\b" + re.escape(step) + r"\s*:", text) is not None,
                f"Missing completed model step: {step}",
            )
        summary = distributions(tables)
        (report_dir / "distributions.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
        baseline_path = ROOT / f"tests/baselines/{args.households}.json"
        baseline = (
            json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
        )
        fallback = sum(map(int, re.findall(r"coercing (\d+) depart choices", text)))
        report = (
            f"# Model validation passed\n\nRuntime: {metadata['seconds']:.1f}s. "
            f"Peak summed process RSS: {peak / 1024**3:.2f} GiB "
            "(shared pages may be counted more than once).\n\n"
            f"Scheduling fallback trips: {fallback}. Warning/error log lines: {len(warnings)}.\n\n"
            + (
                advisory(summary, baseline)
                if baseline
                else "No baseline yet; distributions saved for review."
            )
        )
    except Exception as error:
        report = f"# Model validation failed\n\n{error}\n"
        raise
    finally:
        (report_dir / "summary.md").write_text(report + "\n")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
                stream.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
