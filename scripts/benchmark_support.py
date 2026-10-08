"""Shared benchmark configuration, provenance, and bounded input validation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def table_path(directory, stem):
    # Match ActivitySim's configured CSV first, then its Parquet fallback.
    for suffix in (".csv", ".parquet"):
        path = Path(directory) / f"{stem}{suffix}"
        if path.exists():
            return path
    raise FileNotFoundError(f"Missing {stem}.csv or {stem}.parquet in {directory}")


def batches(path, columns=None):
    import pandas as pd
    import pyarrow.parquet as pq

    if path.suffix == ".parquet":
        for batch in pq.ParquetFile(path).iter_batches(
            batch_size=100_000, columns=columns
        ):
            yield batch.to_pandas()
    else:
        yield from pd.read_csv(path, usecols=columns, chunksize=100_000)


def input_identity(directory):
    paths = [
        table_path(directory, name) for name in ("households", "persons", "land_use")
    ]
    paths += sorted(Path(directory).glob("*.omx"))
    return {
        p.name: {"bytes": p.stat().st_size, "sha256": file_digest(p)} for p in paths
    }


def code_identity(root):
    paths = [root / "uv.lock", root / "pyproject.toml"]
    directories = [root / "scripts", root / "src", root / "model/extensions"]
    directories += sorted((root / "model").glob("configs*"))
    for directory in directories:
        paths += [
            p
            for p in directory.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
    return {str(p.relative_to(root)): file_digest(p) for p in sorted(paths)}


def configs(model_dir, multiprocess, profile):
    result = [model_dir / "configs"]
    if multiprocess:
        result.insert(0, model_dir / "configs_mp")
    if profile == "laptop":
        result.insert(0, model_dir / "configs_explicit_chunk")
    return tuple(result)


def import_extensions(state, model_dir):
    # Spawned ActivitySim workers resolve module names against their process cwd.
    os.chdir(model_dir)
    state.import_extensions("extensions", append=False)
    state.set("run_id", state.tracing.run_id)


def preflight(data_dir, model_dir):
    """Validate production prerequisites without holding full person tables in memory."""
    import numpy as np
    import pandas as pd
    import openmatrix as omx
    import yaml

    def require(condition, message):
        if not condition:
            raise ValueError(f"Input preflight: {message}")

    settings = yaml.safe_load((model_dir / "configs/settings.yaml").read_text())
    for spec in settings["input_table_list"]:
        path = table_path(data_dir, spec["tablename"])
        columns = set(next(batches(path)).columns)
        renames = spec.get("rename_columns", {})
        columns |= {renames.get(c, c) for c in columns}
        required = set(spec.get("keep_columns", [])) | {spec["index_col"]}
        require(
            not required - columns,
            f"{path.name}: missing columns {sorted(required - columns)}",
        )
    land = pd.concat(batches(table_path(data_dir, "land_use")))
    zones = pd.Index(land.TAZ)
    require(zones.is_unique and not zones.hasnans, "invalid land-use zone IDs")
    households = pd.concat(
        batches(
            table_path(data_dir, "households"),
            ["household_id", "hhsize", "income", "TAZ"],
        )
    ).set_index("household_id")
    require(
        households.index.is_unique and not households.index.hasnans,
        "invalid household IDs",
    )
    require(households.TAZ.isin(zones).all(), "unknown household zone")
    require(np.isfinite(households.income).all(), "nonfinite household income")
    rules = yaml.safe_load(
        (model_dir / "configs/constraint_fixed_work_schedule.yaml").read_text()
    )
    sizes = np.zeros(len(households), dtype=np.int64)
    person_ids = []
    for persons in batches(
        table_path(data_dir, "persons"),
        [
            "person_id",
            "household_id",
            "age",
            "pemploy",
            "pstudent",
            "ptype",
            "naics_code",
        ],
    ):
        require(persons.person_id.notna().all(), "missing person IDs")
        person_ids.append(persons.person_id.to_numpy())
        positions = households.index.get_indexer(persons.household_id)
        require((positions >= 0).all(), "persons reference unknown households")
        np.add.at(sizes, positions, 1)
        require(persons.age.between(0, 120).all(), "invalid ages")
        for col, allowed in (
            ("pemploy", "EMPLOYMENT_CODES"),
            ("pstudent", "STUDENT_STATUS_CODES"),
            ("ptype", "PERSON_TYPES"),
        ):
            require(persons[col].isin(rules[allowed]).all(), f"invalid {col}")
        eligible = (
            persons.pemploy.isin(rules["EMPLOYED_CODES"])
            & ~persons.pstudent.isin(rules["STUDENT_CODES"])
            & ~persons.ptype.isin(rules["STUDENT_PERSON_TYPES"])
        )
        require(
            persons.loc[eligible, "naics_code"].isin(rules["INDUSTRY_CODES"]).all(),
            "missing/unsupported eligible-worker naics_code",
        )
    ids = np.concatenate(person_ids)
    require(pd.Index(ids).is_unique, "duplicate person IDs")
    require(
        np.array_equal(sizes, households.hhsize.to_numpy()),
        "household sizes do not match person counts",
    )
    skims = sorted(Path(data_dir).glob("*.omx"))
    require(bool(skims), "no OMX skims")
    for path in skims:
        with omx.open_file(str(path), "r") as matrix:
            require(
                tuple(matrix.shape()) == (len(zones), len(zones)),
                f"{path.name}: wrong skim dimensions",
            )
            mappings = matrix.list_mappings()
            require(bool(mappings), f"{path.name}: missing zone mapping")
            for name in mappings:
                require(
                    set(matrix.mapping(name)) == set(zones),
                    f"{path.name}: zone mapping mismatch",
                )
    return {
        "households": len(households),
        "persons": len(ids),
        "zones": len(zones),
        "skim_files": len(skims),
        "validated": True,
    }


def validate_output_population(data_dir, output_dir, sample_size):
    """Check population identity and output references with projected, batched reads."""
    import numpy as np
    import pandas as pd

    def read(stem, columns, directory=output_dir):
        frames = []
        for frame in batches(table_path(directory, stem), columns):
            if any(c not in frame for c in columns):
                frame = frame.reset_index()
            frames.append(frame[columns])
        return pd.concat(frames, ignore_index=True)

    def require(condition, message):
        if not condition:
            raise ValueError(f"Output validation: {message}")

    households = read("final_households", ["household_id", "hhsize"]).set_index(
        "household_id"
    )
    persons = read("final_persons", ["person_id", "household_id"]).set_index(
        "person_id"
    )
    for name, frame in (("households", households), ("persons", persons)):
        require(
            frame.index.is_unique and not frame.index.hasnans, f"invalid {name} IDs"
        )
    expected_h = read("households", ["household_id"], data_dir).household_id
    require(households.index.isin(expected_h).all(), "unknown households")
    require(
        len(households)
        == (min(sample_size, len(expected_h)) if sample_size else len(expected_h)),
        "household count changed",
    )
    expected_p = read("persons", ["person_id", "household_id"], data_dir)
    expected_p = expected_p.loc[
        expected_p.household_id.isin(households.index)
    ].set_index("person_id")
    require(
        len(persons) == len(expected_p) and persons.index.isin(expected_p.index).all(),
        "person population changed",
    )
    require(
        persons.household_id.equals(expected_p.household_id.reindex(persons.index)),
        "person household changed",
    )
    require(
        persons.groupby("household_id")
        .size()
        .reindex(households.index, fill_value=0)
        .eq(households.hhsize)
        .all(),
        "household sizes differ",
    )
    del expected_p, expected_h
    zones = read("land_use", ["TAZ"], data_dir).TAZ
    tours = read(
        "final_tours", ["tour_id", "person_id", "household_id", "start", "end"]
    ).set_index("tour_id")
    require(tours.index.is_unique and not tours.index.hasnans, "invalid tour IDs")
    require(tours.person_id.isin(persons.index).all(), "unknown tour person")
    require(
        tours.household_id.eq(
            persons.household_id.reindex(tours.person_id).to_numpy()
        ).all(),
        "tour household differs",
    )
    require(
        tours.start.between(1, 24).all()
        and tours.end.between(1, 24).all()
        and tours.start.le(tours.end).all(),
        "invalid tour times",
    )
    trip_ids, toured = [], []
    for name, mode in (("final_tours", "tour_mode"), ("final_trips", "trip_mode")):
        cols = ["origin", "destination", mode]
        if name == "final_trips":
            cols += ["trip_id", "tour_id", "person_id", "household_id", "depart"]
        for frame in batches(table_path(output_dir, name), cols):
            if name == "final_trips" and "trip_id" not in frame:
                frame = frame.reset_index()
            require(
                frame.origin.isin(zones).all() and frame.destination.isin(zones).all(),
                "unknown output zone",
            )
            require(
                frame[mode].notna().all() and frame[mode].astype(str).ne("").all(),
                "missing output mode",
            )
            if name == "final_trips":
                require(frame.tour_id.isin(tours.index).all(), "unknown trip tour")
                require(
                    frame.person_id.eq(
                        tours.person_id.reindex(frame.tour_id).to_numpy()
                    ).all(),
                    "trip owner differs",
                )
                require(
                    frame.household_id.eq(
                        tours.household_id.reindex(frame.tour_id).to_numpy()
                    ).all(),
                    "trip household differs",
                )
                require(frame.depart.between(1, 24).all(), "invalid trip departure")
                trip_ids.append(frame.trip_id.to_numpy())
                toured.append(frame.tour_id.to_numpy())
    ids = pd.Index(np.concatenate(trip_ids))
    require(ids.is_unique and not ids.hasnans, "invalid trip IDs")
    require(
        pd.Index(np.concatenate(toured))
        .unique()
        .sort_values()
        .equals(tours.index.sort_values()),
        "tours missing trips",
    )
    return {
        "validated": True,
        "households": len(households),
        "persons": len(persons),
        "tours": len(tours),
        "trips": len(ids),
        "scope": "population, IDs, ownership, zones, modes, tour times, departure bounds, tour coverage",
    }
