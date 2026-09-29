#!/usr/bin/env python3
"""Impute industries from donor age/employment strata; never match unrelated IDs."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


def naicsp_to_naics(naicsp):
    """Notebook conversion: retain 721/722, special 3MS/4MS, otherwise two digits."""
    if pd.isna(naicsp):
        return None
    code = str(naicsp).strip()
    if code in {"3MS", "4MS"}:
        return {"3MS": "33", "4MS": "45"}[code]
    match = re.match(r"\d+", code)
    if not match or len(match[0]) < 2:
        return None
    digits = match[0]
    return digits[:3] if digits[:3] in {"721", "722"} else digits[:2]


def donor_counts(path):
    pieces = []
    for chunk in pd.read_csv(
        path,
        usecols=["age", "pemploy", "NAICSP"],
        dtype={"NAICSP": "string"},
        chunksize=500_000,
    ):
        if chunk[["age", "pemploy"]].isna().any().any():
            raise ValueError("Donor age and employment must be complete")
        mapping = {
            code: naicsp_to_naics(code) for code in chunk.NAICSP.dropna().unique()
        }
        # Internal category only; serialized as a missing value, not a NAICS code.
        chunk["naics_code"] = chunk.NAICSP.map(mapping).fillna("missing")
        pieces.append(chunk.groupby(["age", "pemploy", "naics_code"]).size())
    return pd.concat(pieces).groupby(level=[0, 1, 2]).sum().sort_index()


def impute(target, counts, seed):
    if target.person_id.isna().any() or not target.person_id.is_unique:
        raise ValueError("Target person IDs must be present and unique")
    if target[["age", "pemploy"]].isna().any().any():
        raise ValueError("Target age and employment must be complete")
    rng = np.random.default_rng(seed)
    result = pd.Series(pd.NA, index=target.index, dtype="Int64", name="naics_code")
    audits = []
    for (age, employment), people in target.groupby(["age", "pemploy"], sort=True):
        try:
            available = counts.xs(employment, level="pemploy")
        except KeyError as error:
            raise ValueError(f"No donors for employment type {employment}") from error
        ages = available.index.get_level_values("age").unique().to_numpy()
        # Exact-age donors are preferred. If absent, use the nearest age of the
        # same employment type; ties choose the younger age and are reported.
        donor_age = min(ages, key=lambda value: (abs(value - age), value))
        distribution = available.xs(donor_age, level="age").sort_index()
        expected = distribution / distribution.sum() * len(people)
        allocated = np.floor(expected).astype(int)
        remainder = len(people) - int(allocated.sum())
        order = np.argsort(-(expected - allocated).to_numpy(), kind="stable")
        allocated.iloc[order[:remainder]] += 1
        values = np.repeat(distribution.index.to_numpy(), allocated.to_numpy())
        rng.shuffle(values)
        # Sorting by ID makes assignment invariant to target CSV row order.
        positions = people.sort_values("person_id").index
        result.loc[positions] = pd.array(
            [None if code == "missing" else int(code) for code in values], dtype="Int64"
        )
        audits.append(
            {
                "age": int(age),
                "pemploy": int(employment),
                "donor_age": int(donor_age),
                "donor_count": int(distribution.sum()),
                "target_count": len(people),
                "donor_proportions": (distribution / distribution.sum()).to_dict(),
                "assigned_counts": {str(k): int(v) for k, v in allocated.items()},
            }
        )
    return result, audits


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--donors", type=Path, default=Path("model/data/extra/persons.csv")
    )
    parser.add_argument("--target", type=Path, default=Path("model/data/persons.csv"))
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument(
        "--report", type=Path, default=Path("model/output_naics_imputation/report.json")
    )
    args = parser.parse_args()
    if args.donors.resolve() == args.target.resolve():
        parser.error("Donor and target files must differ")
    target = pd.read_csv(args.target)
    before = sha256(args.target)
    values, strata = impute(target, donor_counts(args.donors), args.seed)
    original = target.drop(columns="naics_code", errors="ignore").copy()
    target["naics_code"] = values
    temporary = args.target.with_suffix(".imputed.tmp")
    try:
        target.to_csv(temporary, index=False)
        reread = pd.read_csv(temporary)
        pd.testing.assert_frame_equal(original, reread[original.columns])
        temporary.replace(args.target)
    finally:
        temporary.unlink(missing_ok=True)
    report = {
        "method": "Imputed, not observed: largest-remainder allocation within exact age and pemploy; seeded shuffle by sorted person_id; nearest-age fallback within pemploy only.",
        "conversion": "Notebook naicsp_to_naics2, including 3MS/4MS and 721/722. Missing/invalid codes remain missing. No additional military recoding.",
        "seed": args.seed,
        "donors": str(args.donors),
        "donor_sha256": sha256(args.donors),
        "target": str(args.target),
        "target_before_sha256": before,
        "target_after_sha256": sha256(args.target),
        "rows": len(target),
        "missing_naics": int(values.isna().sum()),
        "fallback_strata": sum(s["age"] != s["donor_age"] for s in strata),
        "strata": strata,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"Imputed {len(target):,} people; {values.isna().sum():,} missing industry values."
    )
    print(
        f"Nearest-age fallback strata: {report['fallback_strata']}. Audit: {args.report}"
    )


if __name__ == "__main__":
    main()
