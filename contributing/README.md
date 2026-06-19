# Contributing

The external-contributor lifecycle for
[gastownhall/gascity](https://github.com/gastownhall/gascity), distributed as a
Gas City pack.

It gives an outside contributor the full journey of landing work upstream — and
carries Gas City's **actual** standards at every step. This is not generic PR
discipline: the adoption-review audit (B1–B36), the blast-radius dimensions, the
design-capture rule, the five test tiers, and the code conventions a Gas City
maintainer reviews against are all **baked into the skill text**, so your own
coding agent applies them by reading the skill.

## Self-contained by design

This pack has **no imports** and depends on nothing you might not have — no
internal agents, no sibling pack, no maintainer-only tooling. Every skill is a
self-applicable checklist. You run the workflow with `git`, `gh`, and your
coding agent reading the skills; that's it.

> The generic [pr-pipeline] pack is still the right choice for a city that wants
> contributor discipline without Gas City's particular standards. This pack is
> the gas-city-specific instantiation — it trades portability for baked-in
> standards.

## The lifecycle

| Step | What you do | Skill |
|------|-------------|-------|
| 1 | Write a high-quality issue | [`write-issue`](skills/write-issue/SKILL.md) |
| 2 | Find a priority issue to work on | [`find-work`](skills/find-work/SKILL.md) |
| 3 | Plan the PR (adoption-review-aware) | [`plan-pr`](skills/plan-pr/SKILL.md) |
| 4 | Map the impact surface | [`blast-radius`](skills/blast-radius/SKILL.md) |
| 5 | Run the codebase audit + gates | [`check`](skills/check/SKILL.md) |
| 6 | Self-review before pushing | [`ship`](skills/ship/SKILL.md) |

Two entry points join the same loop:

- **PR a priority issue** — start at step 2 (`find-work` to triage), then plan it.
- **PR your own issue** — start at step 1 (`write-issue`), then plan it.

The [`contributing`](skills/contributing/SKILL.md) skill is the operational map;
it explains both entry points and links each step to its skill.

## Nothing here pushes for you

Each step produces an artifact you act on — an issue body, a plan, a blast-radius
report, an audit verdict, a readiness report. The `ship` skill stops at the
readiness report. **Pushing the branch and opening the PR are your call.**

## Usage

In your city's `pack.toml`:

```toml
[imports.contributing]
source = "../packs/contributing"   # path; or git URL when published
```

Then the skills load for your coding agent. You can also read them directly from
this directory — they're self-contained Markdown.

## Pack contents

```
contributing/
├── pack.toml                       schema=2; no imports (self-contained)
├── README.md
├── skills/
│   ├── contributing/SKILL.md       the lifecycle map (both entry points)
│   ├── write-issue/SKILL.md        file a maintainer-grade issue
│   ├── find-work/SKILL.md          triage open issues into a work-queue
│   ├── plan-pr/SKILL.md            adoption-review-aware PR planning
│   ├── blast-radius/SKILL.md       map the impact surface of a change
│   ├── check/SKILL.md              mechanical gates + the B1–B36 audit
│   └── ship/SKILL.md               pre-push self-review gate
├── doctor/                         preflight checks (gc, gh, git present)
│   ├── check-gc.sh   + gc/doctor.toml
│   ├── check-gh.sh   + gh/doctor.toml
│   └── check-git.sh  + git/doctor.toml
└── tests/
    ├── test_contributing_skill_frontmatter.py   skills have name + description
    └── test_contributing_pack_structure.py      self-contained; doctor scripts executable
```

## Tests

```sh
python3 -m pytest contributing/tests/
```

[pr-pipeline]: https://github.com/gastownhall/gascity-packs/tree/main/pr-pipeline
