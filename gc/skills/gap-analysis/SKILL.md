---
name: gap-analysis
description: Produce a targetless verdict report comparing implementation results to approved requirements and design.
---

# GC Gap Analysis

Use this skill to run the public `gap-analysis` report formula against an
implementation summary, diff, or artifact set.

## Workflow

1. Validate the optional context bundle with
   `assets/scripts/validate_context_bundle.py`.
2. Run the `gap-analysis` formula in report mode. It does not mutate beads,
   branches, source files, or convoys.
3. Validate the output with `assets/scripts/validate_verdict_report.py --kind
   gap-analysis`.

## Launch Contract

```sh
gc sling <review-target> gap-analysis --formula \
  --var subject_path=<summary-or-diff-path> \
  --var report_path=<artifact-root>/gap-analysis.md \
  --var context_path=<optional-context-yaml>
```

The report front matter uses `schema: gc.verdict-report.v1` and `verdict:
pass|fail`.
