---
name: implement
description: Launch convoy-first implementation for an approved implementation convoy.
---

# GC Implement

Use this skill when an implementation convoy already exists and the user wants
to run implementation without the full build loop.

## Workflow

1. Verify the target is a convoy or a normalized singleton convoy.
2. Validate `context_path` with `assets/scripts/validate_context_bundle.py` when one
   is provided.
3. Launch the `implement` graph.v2 formula with the target convoy. Do not pass
   legacy `issue`, `bead_id`, or user-defined `convoy_id` variables.
4. Wait for the drain manifest to finish and report the aggregate summary.

## Launch Contract

```sh
gc sling <coordinator-target> implement --formula \
  --target <convoy-id> \
  --var context_path=<optional-context-yaml> \
  --var drain_policy=separate
```

Valid drain policies are `separate` and `same-session`. `separate` is the
default for standalone use.
