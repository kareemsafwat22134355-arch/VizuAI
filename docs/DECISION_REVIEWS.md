# MONTER Decision Reviews v0.15

`human-corrections.json` answers: **what did the editor change?**

`decision-reviews.json` answers the missing denominator question: **which AI decisions did a human actually review, and were they accepted or corrected?**

MONTER must not infer acceptance/rejection rates from corrections alone. A correction-only collection contains failures but says nothing about how many comparable AI decisions were accepted unchanged.

## Record an accepted decision

```bash
monter-review \
  --project-manifest ".monter/project.monter.json" \
  --reviews ".monter/decision-reviews.json" \
  --kind transition \
  --target-type boundary \
  --target-ref 7 \
  --outcome accepted \
  --ai-json '{"mechanism":"directional_bridge","durationSeconds":0.12}' \
  --context-json '{"directorRole":"build","relationScore":0.81}' \
  --reason "The movement continuity reads naturally."
```

## Record a corrected decision

```bash
monter-review \
  --project-manifest ".monter/project.monter.json" \
  --reviews ".monter/decision-reviews.json" \
  --corrections ".monter/human-corrections.json" \
  --kind transition \
  --target-type boundary \
  --target-ref 8 \
  --outcome corrected \
  --ai-json '{"mechanism":"directional_bridge","durationSeconds":0.12}' \
  --human-json '{"mechanism":"hard_cut","durationSeconds":0}' \
  --context-json '{"directorRole":"rupture","relationScore":0.76}' \
  --reason "The rupture should remain abrupt."
```

A corrected review creates the human correction and stores only its `correctionId` in the review event. The human replacement decision therefore has one canonical source of truth.

## Build a summary

```bash
monter-review-summary \
  --reviews ".monter/decision-reviews.json" \
  --corrections ".monter/human-corrections.json" \
  --out ".monter/decision-review-summary.json"
```

The summary reports:

- total reviewed / accepted / corrected
- acceptance rate using **all reviewed decisions** as denominator
- rates by decision kind
- rates by `directorRole` when that context was recorded
- transition acceptance rates by the AI-proposed `mechanism`

Buckets with fewer than five reviewed decisions are explicitly marked low-sample and must remain descriptive.

## Relationship to learning

Decision review rates are evidence, not policy. A pattern such as “directional_bridge accepted 2/10 in rupture sections” can justify a later hypothesis or policy experiment, but v0.15 never rewrites planner/compiler behavior automatically.

Before a review-derived rule can affect production, MONTER should require:

1. sufficient reviewed sample count,
2. a context-specific hypothesis,
3. benchmark comparison against held-out projects,
4. no regression on other critic dimensions,
5. explicit versioned policy change.

This keeps human feedback traceable and prevents a handful of project-specific edits from becoming accidental global taste rules.
