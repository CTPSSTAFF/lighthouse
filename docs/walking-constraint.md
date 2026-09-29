# Person walking constraint

`constraint_walk_ability` assigns `can_walk_far` once per person, after
`constraint_can_travel_alone` and before school/work location choice. Both the single-process and
multiprocess model sequences use this order. The assignment uses ActivitySim's person random
channel, so it is reproducible for a fixed seed and person ID across row order and process
partitions.

The probabilities in `model/configs/constraint_walk_ability.yaml` are user-specified scenario
assumptions, not estimated or behaviorally validated parameters:

- Under 65: 100% capability.
- Ages 65–79: 50% capability.
- Ages 80+: 20% capability.
- Any adult (18+) with `can_travel_alone = False`: 0%, overriding age.

The age probabilities apply to people who are not subject to the override. They are probabilities,
not exact population quotas; final age-group capability shares can be lower because of the override.
Children are not restricted solely because they cannot travel alone. Invalid/missing ages or
travel-alone flags raise an error rather than silently assigning a capability.

People without capability receive `walk_distance_limit = 0.15` miles. Capable people receive
infinity, leaving the existing mode-specific distance rules unchanged. These columns persist on
`persons` and are passed to mode-choice choosers. Exactly 0.15 miles is permitted.

## Consumers

- WALK tour choice checks the larger of outbound and return `dist_nm` distances. School/work and
  other destination-choice logsums use the same tour specification.
- WALK trip choice checks the trip's `dist_nm`, regardless of its tour mode.
- Intermediate destinations on WALK tours check both origin-to-stop and stop-to-tour-leg-destination
  distances in sampling and final destination choice.
- WALK_TRANSIT checks the skimmed walking portion of each one-way transit trip. Tour choice checks
  both directions separately; intermediate destination logsums check each candidate leg using the
  trip specification. Other feasible trip modes remain available under the existing tour-mode rules.

Transit walking distance is `tw_walk * WALK_TRANSIT_WALK_MINUTES_PER_UNIT * walkSpeed / 60`. The
conversion factor in `constants.yaml` is 1.0, matching the raw-minute treatment of `tw_walk` in the
active tour/trip WALK_TRANSIT utility expressions. At 3 mph, 0.15 miles corresponds to 3 minutes.
This uses aggregate skimmed walking per transit trip, not an individual access, transfer, or egress
segment: the supplied skims do not separate these segments. The legacy summary preprocessor applies
a different scaling convention; it is not used for this rule. Confirm skim units when substituting
new networks. DRIVE_TRANSIT and its walking portions are outside this change's agreed scope.

Restrictions use the model's existing -999 unavailable-utility convention. Tests check that the new
penalties produce zero probability relative to available alternatives at the distance boundaries;
small full-model runs should additionally be checked for selected-mode violations. As with other
finite-penalty rules, this is not a general exact-exclusion guarantee under arbitrary utilities.

The current configured model generates individual tours, not joint tours. If joint tour generation
is enabled later, capability must be aggregated across participants before applying this
person-based rule to a shared tour; the current merged chooser tables identify the tour owner.

## Validation and running

From the repository root, use the documented local development runner for this checkout's sibling
ActivitySim/Sharrow sources:

```sh
python uv-local python -m pytest tests/test_walk_ability.py -q
python uv-local activitysim run -c model/configs_mp -c model/configs -d model/data \
  -o model/output_walk_check --ext extensions
```

The focused tests cover age boundaries, the adult override, invalid/empty inputs, persistence,
probability shares, row-order and two-process repeatability, actual CSV specification evaluation,
distance boundaries, and return-direction checks. They validate implementation, not the empirical
credibility of the scenario probabilities.

### Validation on the current checkout

The 14 focused tests passed using the local development runner. Full single-process and two-worker
runs on the first 100 frozen fixture households completed: 230 people, 264 tours, and 660 trips.
There were 115 people subject to the limit. Both runs had zero selected WALK/WALK_TRANSIT violations
when checked against the runtime skim lookups, and identical travel-alone/walking capability
assignments. Python lint/format checks and Markdown formatting also passed. The new constraint YAML
passes strict yamllint; existing settings files retain pre-existing style violations (line lengths,
indentation, and trailing whitespace).

Those original full runs used the sibling-source development environment. The subsequent backend
compatibility fix moved the trip-mode `explicit_chunk` option into an optional development overlay,
so the base model and Sharrow overlay can also run with the locked released dependencies.

**Zone alignment correction:** the mismatch found during the original walking-constraint validation
was caused by running the non-Sharrow skim dictionary with recoded zone positions. Lighthouse now
uses original zone IDs when Sharrow is off and enables recoding only in `configs_sh`. Both backends
are checked against known OMX mappings and compared in CI; see
[Execution backends](execution-backends.md). The former runtime-only walking validation is
historical, not evidence that the old geographically misaligned configuration was correct.
