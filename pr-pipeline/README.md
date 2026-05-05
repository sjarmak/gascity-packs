# PR Pipeline

Author-side and review-side PR discipline distributed as a Gas City pack.

Encodes the planning, blast-radius, scorecard-review, and pre-push gating
workflows that careful contributors run by hand, so any city that imports
this pack gets the same discipline as platform-native formulas and commands.

## Status

**v0.1.0** — first slice, planner only. Subsequent versions add:

- `mol-pr-blast-radius` — caller-graph and concurrency-surface mapping
  (currently inlined in the planner; later promoted to its own formula
  for use independent of the full planning workflow)
- `mol-pr-review` — 11-category structured review for outgoing PRs
- `mol-pr-ship` — pre-push gate (simplify → review → conventions check)

## Sibling pack

`pr-review` (in this same repo) covers the **maintainer-side incoming-PR
review/merge workflow** with `mol-adopt-pr` — a 6-step formula for
adopting contributor PRs (intake → rebase → review → human-gate →
finalize → merge). The two packs are complementary:

- `pr-review` → reviewing PRs that arrive at your repo
- `pr-pipeline` → planning, building, and shipping PRs your city sends out

A city that does both ("we contribute to repos and we accept contributions
from others") imports both.

## Usage

In your city's `pack.toml`:

```toml
[imports.pr-pipeline]
source = "../packs/pr-pipeline"  # or git URL when published
```

Plan a PR for an issue (the rig's repo contains the issue's code):

```sh
gc pr-pipeline pr plan 1234 --rig api-server
```

Or directly via sling:

```sh
gc sling api-server/polecat mol-pr-start --formula --var issue=1234
```

Default agent for the wrapper command is `polecat`; override with
`--agent <name>` if your city uses a different worker pool name.

The formula reads the issue, runs BLOCKING gates (competing-PR and
architectural-refactor checks), maps blast radius, checks the repo's
conventions, writes a structured plan to
`.gc/pr-pipeline/plans/issue-1234.md`, and audits the plan against
19 recurring review findings. **No code is written.** A separate sling
or human picks up the plan to implement it.

## Pack contents

```
pr-pipeline/
├── pack.toml
├── formulas/
│   └── mol-pr-start.formula.toml    6-step planner workflow
└── commands/
    └── pr/plan/                     gc <binding> pr plan
        ├── run.sh
        └── help.md
```

The full workflow (BLOCKING gates, blast-radius mapping, convention
alignment, plan production, themes audit) lives in the formula's step
descriptions. A coding agent (polecat or equivalent) follows them in
sequence; gates can short-circuit with an early exit.

## Why formula-shaped, not agent-as-directory

This pack ships **formulas**, not standing agents. The planner is a
bounded workflow ("plan one PR, exit"), not a long-lived role like
mayor or polecat. The consumer city's existing coding worker (whatever
it's named) runs the formula — no extra agent deployment required.

Standing roles (mayor, polecat, witness, refinery) belong in their own
packs as `agents/<name>/` directories. Bounded workflows belong as
`formulas/mol-<name>.formula.toml` with the workflow inlined in step
descriptions.
