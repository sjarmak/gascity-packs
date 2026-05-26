---
name: review
description: Produce a targetless implementation review verdict report for a diff, branch, or artifact set.
---

# GC Review

Use this skill to run the public `review` report formula against an
implementation summary, diff, branch, or artifact set.

## Workflow

1. Validate the optional context bundle with
   `assets/scripts/validate_context_bundle.py`.
2. Run the `review` formula in report mode. It does not mutate beads,
   branches, source files, or convoys.
3. Validate the output with `assets/scripts/validate_verdict_report.py --kind review`.

## Launch Contract

```sh
gc sling <review-target> review --formula \
  --var subject_path=<diff-branch-or-artifact-path> \
  --var report_path=<artifact-root>/review.md \
  --var context_path=<optional-context-yaml>
```

The report front matter uses `schema: gc.verdict-report.v1` and `verdict:
pass|fail`.
