---
name: contributing
description: The full external-contributor lifecycle for gastownhall/gascity — write a good issue, find priority work, plan a PR, map its blast radius, run the codebase audit, and self-review before pushing. Use when someone wants to contribute to Gas City and needs to know which step they're on and which skill runs it. Self-contained: every step is a skill in this pack with Gas City's actual standards baked in — no internal tooling, no sibling pack.
---

# Contributing to Gas City

You are an external contributor to
[gastownhall/gascity](https://github.com/gastownhall/gascity). This skill is the
map of the whole journey — from "I noticed something" to "my PR is ready to
push" — and which skill runs each step.

Everything lives in this one pack. Each step carries Gas City's **actual**
standards (the adoption-review audit, the blast-radius dimensions, the
design-capture rule, the test tiers) baked into the skill text, so your coding
agent applies them by reading. There's nothing to install beyond `git`, `gh`, and
a local checkout.

Nothing here pushes a branch or opens a PR for you — those stay your explicit
call. Each step produces an artifact (an issue, a plan, a report) you act on.

## The lifecycle

```
   ┌─ 1. write a good issue ───────────────┐   (write-issue)
   │                                        │
   │   ┌─ 2. find priority work ────────┐   │   (find-work)
   │   │                                │   │
   ▼   ▼                                │   │
   3. plan the PR ──────────────────────┘   │   (plan-pr)
   │                                        │
   ▼                                        │
   4. map blast radius                      │   (blast-radius)
   │                                        │
   ▼                                        │
   5. run the codebase check                │   (check)
   │                                        │
   ▼                                        │
   6. self-review before pushing ◀──────────┘   (ship)
```

| Step | What you do | Skill |
|------|-------------|-------|
| 1 | Write a high-quality issue | [write-issue](../write-issue/SKILL.md) |
| 2 | Find a priority issue to work on | [find-work](../find-work/SKILL.md) |
| 3 | Plan the PR (adoption-review-aware) | [plan-pr](../plan-pr/SKILL.md) |
| 4 | Map the impact surface | [blast-radius](../blast-radius/SKILL.md) |
| 5 | Run mechanical gates + the B1–B36 audit | [check](../check/SKILL.md) |
| 6 | Self-review and produce a readiness report | [ship](../ship/SKILL.md) |

## Two entry points

The lifecycle is one loop; you join it at different places depending on what
you're starting from.

### A. PR a priority issue (someone else's issue, or a triage pick)

You want to help but don't have a specific bug in mind. Start at **step 2**.

1. **Find work** — run [find-work](../find-work/SKILL.md) to scan open issues,
   rank them into a contributor work-queue, and filter out anything already
   covered by an open PR or blocked on a maintainer decision. Pick an unassigned,
   in-scope issue that passes the decision gates.
2. **Plan the PR** for the issue you picked — go to **step 3**.

### B. PR your own issue (something you found)

You hit a bug or have a change in mind. Start at **step 1**.

1. **Write the issue** first with [write-issue](../write-issue/SKILL.md). Filing
   it before you code gives a maintainer a chance to redirect the approach, flag a
   duplicate, or point at a design constraint — far cheaper than finding that out
   on the PR.
2. **Plan the PR** on the issue you just filed — go to **step 3**.

## Step 3 — plan the PR

Both entry points converge here; you have an issue number. Run
[plan-pr](../plan-pr/SKILL.md). It front-loads the analysis the maintainer's
review will check — the competing-PR and architectural-refactor gates, blast
radius, convention alignment, the design-capture decision, and a plan audited
against the recurring review findings. **No code is written until the plan is
confirmed.**

## Step 4 — map blast radius

For any change that isn't trivially local — refactors, anything touching shared
state, lifecycle, config, or dispatch — run [blast-radius](../blast-radius/SKILL.md)
to map callers, execution contexts, config-field sync chains, domain boundaries,
and concurrency before you write the code. (plan-pr calls this in as its Phase 2.)

## Step 5 — implement, then check

Implement against the plan, keeping the change scoped to what the issue asks
(note anything adjacent as out-of-scope). Then run [check](../check/SKILL.md): the
mechanical gates (`make build` / `make check` / `make check-docs`) with
baseline-vs-regression classification, plus the full B1–B36 codebase audit.

## Step 6 — self-review before pushing

Run [ship](../ship/SKILL.md): the design-capture gate, a simplify pass, a
self-review loop against the recurring adoption-review findings, optional
performance measurement, and the check skill — combined into one readiness
report. **It stops at the report. Pushing the branch and opening the PR are your
call.**

## Notes

- The whole pack is self-contained — no `[imports.*]`, no internal agents, no
  maintainer-only tooling. If you can read these skills and run `git`/`gh`, you
  have everything.
- This is the gas-city-specific lifecycle. A city wanting generic contributor
  discipline without Gas City's particular standards can use the `pr-pipeline`
  pack instead; this pack bakes those standards in.
