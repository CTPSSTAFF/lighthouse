# Industry imputation for the test population

The `naics_code` values added to `model/data/persons.csv` are imputed for model testing, not
observations of those people's actual industries. Person IDs in the donor population are not a valid
crosswalk to this test population.

Run from the repository root, with the donor persons file supplied locally:

```sh
./uv-local python scripts/impute-naics.py
```

The script reads `model/data/extra/persons.csv`, using its existing `age`, `pemploy`, and `NAICSP`
columns. `pemploy` distinguishes full-time workers, part-time workers, nonworkers, and children
under 16 using the population conversion's employment classification. Household attributes are not
needed for this age/employment matching; the extra households file is left unchanged.

Industry conversion follows `notebooks/convert_urbansim_to_activitysim.ipynb`: `3MS` maps to `33`,
`4MS` to `45`, accommodation and food-service codes retain `721` and `722`, and other codes retain
their first two leading digits. Missing and invalid values, including `-1`, remain missing. This
retains the notebook's treatment of military codes; it does not introduce a new mapping to `9000`.

For each exact-age and employment-type group, industry counts (including missing values) are
allocated in proportion to the donor counts. Largest-remainder rounding preserves the group size
while keeping each industry's count within one person of the fractional target. A seeded shuffle
assigns those values to people sorted by person ID. The default seed is `20260922`; results are
reproducible and independent of target row ordering. If an age lacks donors, the nearest age within
the same employment type is used and reported, with younger ages winning ties. Missing employment
types are an error.

The script replaces or appends only the `naics_code` column, verifying the other columns after CSV
serialization. It writes the method, seed, input/output hashes, donor shares, assigned counts, and
fallback usage to `model/output_naics_imputation/report.json`. Keep a separate backup if needed
before running it against other input files. Paths and seed can be overridden with command-line
options.

The initial assignment covered 1,074,799 people in 250 age/employment strata with no fallback. All
581,812 full-time/part-time workers received a code. There were 353,577 missing values among the
other employment categories, reflecting the donors. The original local CSV was preserved at
`model/output_naics_imputation/persons.before.csv`. Backup and audit outputs are ignored by Git; the
raw donor files should not be committed as part of this change.

This preparation supports a software smoke test. It does not preserve actual employer identities,
geographic industry patterns, household correlations, or validate telework behavior. Updated
observed or synthesized production inputs should replace it for substantive forecasting.
