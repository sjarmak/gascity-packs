# The instrument contract

> Packaged from the city this convention was written in, unedited apart from
> this note. The bracketed identifiers throughout (`dr-bovb`, `gc-o8f9m`, and
> the rest) are that city's incident records, and you cannot look them up. They
> are kept anyway: every clause below exists because a specific instrument lied
> in a specific way, and a rule that names its incident is checkable in a way an
> abstract rule is not. The tools named in the examples (`gc-capacity`, the
> reapers, the reports under `.gc-reports/`) are that city's; read them as the
> shape of the failure, not as files you are expected to have.

An **instrument** is anything in this city whose output is read as evidence
about the city: a check, a reaper, a surfacer, a patrol, an order, a doctor
check, a health script, a dashboard number. If a human or an agent will act
differently depending on what it says, it is an instrument and this contract
binds it.

## Why there is a contract at all

Ten separate bugs were filed against this city's checks in a single week. They
look like ten bugs. They are one property:

> **Our instruments report on themselves, and they fail silently toward "fine".**
> None of them fails toward "unknown".

That is what makes it architectural rather than a backlog. A system whose
failures are all silent has an observability layer that is *worse than none*,
because none would at least not be trusted.

The cost is concrete. `bin/seat-recycle` watched a session ID that never
changes for a named seat, so it printed `FAIL: no successor session` on every
recycle that in fact worked (dr-bovb). The remedy the operator learned was to
ignore the instrument. That is the real damage: a false positive is not milder
than a false negative, because the standing fix for both is *stop reading it*.

The pattern is not confined to the instruments themselves. `bin/instrument-inventory`,
written to find this exact defect, committed it four times before its own
output could be trusted, each time by reporting its own blind spot as a
property of the city. That history is in `bin/instrument-inventory.test`.
Assume you will do the same and design so it shows.

---

## The contract

### C1. Report on every run, including the runs that find nothing.

A clean run must produce a record. "No output" must never be the encoding of
"nothing to report", because it is indistinguishable from not having run, from
having crashed before the check, and from the log path being wrong.

`bin/tmp-reaper` gets this right: `REAPED 0` appears 1310 times in its log.
That line is what makes its silence, on the day it goes silent, mean something.

### C2. Distinguish "checked, clean" from "did not check".

The canonical statement of this rule is not here. It is in
`docs/conventions/distributed-systems-optimization.md`, which says it three
times because it is the rule everything else rests on:

> Classify a failed observation as `UNKNOWN` or `LOOKUP_FAILED`, never `ABSENT`.
>
> No cleanup may translate `LOOKUP_FAILED` or `UNKNOWN` into `ABSENT`.
>
> Unknowns remain explicit; they are not converted into reassuring conclusions.

Use that vocabulary. The three values are not stylistic:

- **ABSENT** is a positive finding. You looked in the right place and there was
  nothing there.
- **LOOKUP_FAILED** means you could not look. The channel was unreadable, the
  command failed, the path was outside your reach.
- **UNKNOWN** means you looked and cannot tell.

An instrument that can only say ABSENT has one bit where it needs three, and
the missing two both collapse into the reassuring one. Every instrument defect
logged on 2026-08-08 was this single rule violated: a failed `git` call
returning an empty diff so LOOKUP_FAILED rendered as ABSENT; an ownership test
reading "no remote = ours" when `git remote -v` on a non-repo prints nothing
and exits 128, failing *open* into the permissive bucket; `gc-capacity` serving
a two-hour cache as current state; a restore hook exiting silent on an empty run
so "checked, clean" was byte-identical to "never ran".

Concretely: the instrument needs a third outcome. Not `pass` / `fail`, but
`pass` / `fail` / `could-not-check`, and the third one must be reachable and
must be *emitted*, not swallowed.

Of 60 instruments in this city with a readable log, **18 have never once been
observed emitting an unable-to-check outcome** across their entire recorded
history. Every reading any of them has ever produced was a claim about the city.
None was ever a claim about itself.

Corollary, which is where this usually breaks in practice: **the health
artifact must not be written only on success.** If the file, the mail, or the
metric appears only when the check completed, then its absence is ambiguous and
its presence is the only signal, so the instrument can only ever say "fine".

### C3. It has been made to fail on purpose, and the failure was observed.

**A check that has only ever been observed passing has not been tested.** Not
"has weak coverage". Has not been tested. There is no evidence it can produce
any output other than the one you have seen.

The mechanical form: the test that ships with the instrument contains at least
one case that is RED against the pre-fix or mis-wired instrument, and that
redness has been *observed by running it*, not asserted in a comment. Revert
the fix, watch the test fail, restore the fix, watch it pass, and say so in the
commit.

Ten instruments in this city have a single outcome in their entire recorded
vocabulary. `stale-scix-mcp-reaper` has written exactly one line, ever, and that
line is `stale_detected`. Nobody knows what it does when nothing is stale.

The clause caught the person who wrote it, on the day he wrote it. Mayor's
first regression test for the per-seat working-set fix (dr-xahou, 2ec5c24)
**passed with the defect reintroduced**. Two assertions were bad: one checked
files the test had planted itself rather than anything the hook resolved, and
the other passed only because the seat it happened to check wrote the shared
file last. Nothing about reading that suite revealed it. Making it fail on
purpose did. Treat "I read the test and it looks right" as unverified.

And the failure is default, not exceptional: on 2026-08-08 every instrument
audited against this contract failed C3 before it was touched — `seat-recycle`
had no test at all, and `resource-observability-sample`,
`order-firing-watchdog` and `coordinator-outcome-surfacer` all had suites that
had only ever been observed passing. Four for four, including the watchdog
whose entire job is to notice silence.

### C4. Report the effect you measured, not the action you attempted.

An instrument that reports "I sent the restart" is reporting its own intent.
The evidence is whether the thing restarted. `bin/seat-recycle` requested a
handoff and then watched the wrong variable for the effect; the request
succeeded, the effect happened, and the instrument reported failure (dr-bovb).

### C5. Name the quantity you actually measure.

The `MCP fan-out` alert is threshold `>60 procs or >2.5G`. The proc arm has
never fired; the memory arm fires constantly, at 4 processes against a
sixty-process guard. An alert named for fan-out has fired hundreds of times
without ever reporting fan-out (dr-wa5s). If the name and the measured quantity
disagree, every firing is mislabeled, and splitting the arms is half the fix.

### C6. Every reading carries its own age and its own source.

A number with no timestamp and no provenance cannot be distinguished from a
cached number, a default, or a stale one. This is how a capacity reading of 0%
survives next to an observed rate limit.

### C7. An empty result is not an answer until the corpus is proven non-empty.

This is C2 one layer out: an unproven corpus makes every clean result a
LOOKUP_FAILED wearing an ABSENT label.

"Found nothing" and "looked at nothing" render identically. Before reporting a
clean sweep, the instrument must establish that it had something to sweep:
count the corpus, print the count, and treat a zero corpus as
`could-not-check`, never as clean.

It is the one that keeps recurring: **a check that passes because it is looking
in the wrong place.** The 2026-08-08 canonical-store incident is the reference case. The isolation
check was "confirm the canonical port appears nowhere in your commands." It
passed. The redirect was in an environment variable, invisible to a grep over
files and argv. Configuring the target correctly is not evidence that the tool
is using the configuration. See `docs/conventions/store-sandbox-isolation.md`.

### C8. Prove the destination with a positive AND a negative discriminator.

Where an instrument asserts that something is *here* and not *there*, one half
is not proof. "It is in the sandbox" alone passes if the write went to both.
"It is not in canonical" alone passes if the write failed entirely. Check both
sides. `bin/store-sandbox-verify` gate 3 is the worked example.

### C9. Segment expected states from actionable ones, and read the expectation
from state rather than hardcoding it.

An instrument that reports 307 findings of which 305 are expected under a
disarm the instrument does not know about has buried its two real findings
(dr-cign). Report `2 actionable, 305 expected-under-disarm`, alert only on the
actionable set, and read the disarm from the disposition record.

**Where no such record exists, say so and stop.** The reading half of C9 was
specified for `coordinator-outcome-surfacer` against a disarm record that turned
out not to exist anywhere: the gate is a decision described in a prose report,
with no key, file, or field an instrument could read. The correct outcome was
the one the implementing seat took — leave the value hardcoded, name where it
came from, and report the item as unbuildable as specified. Synthesizing a state
source to satisfy a contract clause produces an instrument that is wrong
invisibly, which is strictly worse than one that is wrong in the open. A wanted
item can be withdrawn; a fabricated input cannot be un-read.

**And when the state you would read is written by the party being watched,
classify and PRINT — never filter.** The segmentation C9 asks for is a
suppression mechanism, so the question of who controls its input is a control
question, not a style one. `bin/mayor-health-surfacer` reported one
`WORK_STALLED` finding, `dr-knrjg.1`, quiet on purpose under `gc.hold_reason`
(a Stephanie-directed pause). The one-line fix is
`select(.metadata["gc.hold_reason"] == "")` — and it hands every worker a mute
button for the instrument watching it, because that key is mutable metadata a
bead writes about itself. Same unsafe-control shape as the review record that
minted its own `reviewer_verdict` (CLAUDE.md, review-gate ruling).

So held, waived, and excepted items move to their own section with the reason
rendered, outside whatever set the alerting layer pages on. The reason then gets
READ rather than trusted, and an exception nobody ever lifted stays visible
instead of decaying into silence. Landed as the `WORK_HELD` section in
`bin/mayor-health-surfacer` (`07c3c82`), outside `stall-watch`'s `pushable()`
set. Both rails proven by mutation per C3: re-merging held rows into the stall
list, and excluding them outright, each turn a different assertion red
(`bin/mayor-health-surfacer.test`, the block titled *a declared hold is
separated from a stall, not hidden by it*).

This does not contradict C9's disarm case: a disposition record written by the
operator disarming the work is a different thing from a key the watched item
writes about itself. Ask who can write the field, not what it means.

### C10. Cover transitions, not only states.

A sampler that only reports current state cannot see a thing that went wrong
and recovered between samples. Where the failure is an edge, record the edge.

### C11. Absence is a signal, and something outside the instrument must watch
for it.

Presence of errors is the half of observability we have; absence of expected
activity is the half we do not. The playbook's table
(`distributed-systems-optimization.md`, Phase 4) is the reference — ready work
exists so claims should begin, and a claim rate of zero is anomalous; running
agents exist so heartbeats should appear; completed work exists so deliveries
should occur.

Its warning is load-bearing for anything built this week: **prevent false
absence alerts with explicit maintenance, paused-admission and
dependency-unavailable states.** The fleet is deliberately limited right now,
which is a paused-admission state. An absence alarm that does not know that
will scream, and the remedy the operator learns will be to ignore it (see the
false-positive note under C4).

The self-heal corollary. The order scheduler wedged for 8h45m with zero orders firing fleet-wide while
the supervisor process stayed up, and recovered only by reboot (dr-1ehw). No
in-process watchdog can catch that, because it shares the wedged loop. The
liveness check for an instrument must run on an independent timer.

C1 is what makes this possible: an instrument that reports on clean runs has a
rate, and a rate that drops to zero is detectable from outside without knowing
anything about what the instrument does.

---

### C12. Map an imported vocabulary to ours, and confirm the mapping on
something you already know is careful.

Grepping a foreign document's terms **inverts**: it reports the most careful
components as unprotected, because careful code was written before the book
arrived and uses this codebase's words. A zero-hit grep for foreign terminology
is LOOKUP_FAILED, never ABSENT — the C2 rule turned back on the auditor using it.

Mayor nearly published a false P0 twenty minutes after adopting the playbook:
`grep -rln -E 'generation|claim_token|row_lock' bin/*reaper*` returned zero hits
across 53 reapers. The protections are all there under our names —
`orphaned-molecule-reaper:101-109` fails closed on an empty session inventory,
`:182-187` maintains `STEP_CLAIMED_BY` and refuses to close a step a different
live root claims. Neither says "generation". Meanwhile the one genuinely
unfenced path was found by **reading**, not by grepping.

This gate committed the same error against the same file: it called
`orphaned-molecule-reaper` untested because its suite marks red cases by citing
the incidents they reproduce (`dr-of5r`, `gc-o8f9m`, `gc-l6m5y`) rather than by
using the word RED. A case tied to a real incident is *better* evidence than one
tied to a keyword.

**The rule: before auditing against an imported document, write the vocabulary
mapping down, then run it against a component you already know is careful. If
your mapping says `orphaned-molecule-reaper` is unprotected, your mapping is
wrong, not the reaper.** Classify by behaviour, never by whether the source
contains a keyword.

Working draft of the mapping, from the mayor — correct it, do not inherit it:

| playbook term    | our term(s)                                          |
| ---------------- | ---------------------------------------------------- |
| generation       | step ref / root bead id / `gc.step_ref` claim         |
| claim token      | session identity, assignee + holder token             |
| destination fence| `STEP_CLAIMED_BY`, the close gate, pool-claim hook    |
| ABSENT vs UNKNOWN| the empty-inventory guard (already implemented)        |
| lease expiry     | seat drain, session TTL, reaper age thresholds        |

### C13. A refuting command must survive the edit that writes it down.

C6 says every reading carries its source. This is the failure one step later: the
source is carried, and the command that expresses it decays. **A refutation
command that pins a line number in a file it lives inside is invalid the moment
any line is inserted above it, including the insertion of the note itself.**

The failure is silent in the worst way. A wrong line number does not error; it
blames a different line and returns a plausible result, and the specific number
makes it read as more authoritative than a vaguer pointer would.

Caught 2026-08-17 in `city.toml`. The mayor added a note explaining that the
polecat pool's `suspended = true` is a deliberate containment rather than stale
config, and cited `git blame -L 1578,1578 -- city.toml` as the reading that
settles it. Writing the eleven-line note pushed the value to 1587, so the command
was wrong before the commit landed. Rivet then reproduced the failure while
trying to *use* it: blamed 1584, corrected to 1588, and only reached the real
line on the third try, each wrong attempt returning a clean blame result. A
follow-up fix moved the line again, to 1590.

**The rule: anchor on content, never on a line number, whenever the note might
move what it points at.** The fix pattern, from `b425fd4`:

```sh
n=$(awk '/^name = "polecat"/{f=1} f&&/^suspended/{print NR;exit}' city.toml)
git blame -L "$n,$n" -- city.toml
```

This is not confined to `git blame`. Any `sed -n 'N,Mp'`, `head -N | tail -1`, or
`-L N,N` in durable prose has the same decay, and so does a bare `file.go:412`
cited as evidence in a bead or a review. Citing a line to help a reader navigate
is fine; citing one as the command that would refute the claim is not.

Recorded twice as a memory before it was written here, and committed anyway on
2026-08-17 by the seat that held the memory. That is the argument for it being a
contract clause rather than a seventh recording.

## When a wanted instrument is unbuildable as specified

A request can name a state the instrument is supposed to read, and that state
can simply not exist anywhere. The correct outcome is to say so and stop, not to
synthesize a source that looks plausible.

Established 2026-08-09 (dr-cign, third WANTED item, withdrawn by the mayor who
wrote it). The item was specified against an "outcome-worker activation
decision" gate. Tracing it: `coordinator-outcome-surfacer:1024` names the gate
and cites a **prose report** in `.gc-reports/`. There is no mayor-settable
record, no key, no file an instrument could read. The specification assumed a
state source that had never been created.

The mayor's ruling, and the reason it generalises past that bead:

> an instrument that reads a guessed state source is worse than one that
> hardcodes a value and says where the value came from, because the first is
> wrong invisibly and the second is wrong in the open.

So, when the state an item names cannot be located:

- **Say the item is unbuildable as specified.** That closes it honestly. It is
  not a gap in your pass and it is not something to leave open and drifting.
- **Do not invent the source.** Do not read an adjacent key that is "close
  enough", do not parse the prose report, do not derive the state from
  behaviour that correlates with it.
- If a hardcoded value is genuinely the right answer for now, hardcode it and
  **name in the source where the value came from and who can change it**.
- The record has to be created *before* the reader, by whoever holds the
  decision. Until then there is nothing to read.

One caution on building it later: a state file with exactly one possible value
is a mechanism pretending to be a measurement. Under skeleton crew several of
these gates have one value, and wiring a reader to them buys the appearance of
a check and none of the substance.

This is the same failure the ABSENT / LOOKUP\_FAILED / UNKNOWN vocabulary exists
for, one level up: there, the instrument cannot read a state that exists; here,
the state does not exist at all. Both are answered by reporting the gap, never
by producing a confident value.

## The gate for a new instrument

Before an instrument is merged, or before its output is trusted:

```bash
bin/instrument-contract-check <path-to-instrument> [more...]
bin/instrument-contract-check --changed        # everything staged/modified
```

It reports on every run including a clean one, prints the corpus it examined,
and **prints the clauses it cannot mechanically check** rather than passing
silently on them. C4, C5, C6, C9 and C10 are judgment clauses; the checker says
so instead of implying it verified them.

What it does check mechanically:

It decides exactly **one** thing: whether a sibling test file exists at all.
That is a filesystem fact and its absence is the only thing that fails the gate.

Everything else is a keyword scan, and per C12 a scan that finds nothing is
reported as **LOOKUP_FAILED**, never as a finding:

| Clause | What the scan looks for | A miss means |
|--------|-------------------------|--------------|
| C1 | emits on a path where the finding set is empty | read the source |
| C2 | a reachable could-not-check outcome | read the source |
| C3 | a marked red case (RED, `red()`, or a cited incident bead ID) | read the test |
| C7 | counts and reports its corpus before calling it clean | read the source |
| C11 | writes a dated line on every run | read the source |

A hit is evidence to read, not proof. `C3 marker found` does not mean the case
was ever observed red; only reverting the fix and watching it fail does.

A failing gate is not a merge blocker by itself. It is a statement that the
instrument's green is not yet evidence, which is exactly the fact this contract
exists to keep visible.

## Auditing what already exists

`bin/instrument-inventory` enumerates every order, doctor check and exec in
this city **from the filesystem** (`gc order check --json`, `orders/*.toml`,
`city.toml [[doctor.check]]`, `gc order history --json`) and answers C1, C2 and
C3 for each. Never enumerate instruments by name-matching: naming heuristics
have inverted on us three times in this city and always on the real offenders.

Latest report: `.gc-reports/instrument-inventory-<date>.txt`.

## Where this sits

`docs/conventions/distributed-systems-optimization.md` is the parent document.
It owns the observation vocabulary (C2), destination-validated mutation
authority, the polling taxonomy (classes A-E) and the absence table (C11). This
contract is the instrument-level application of it: what a single check, reaper
or surfacer must do to be worth reading. When the two appear to disagree, the
playbook wins and this file is the bug.

## Related

- `docs/conventions/distributed-systems-optimization.md` — the parent playbook
- `bin/instrument-inventory`, `bin/instrument-inventory.test`
- `bin/instrument-contract-check`, `bin/instrument-contract-check.test`
- `docs/conventions/store-sandbox-isolation.md` — C7/C8 worked example
- `docs/conventions/scanners.md` — reaper and surfacer rules
- Program bead: dr-zdx10 (observability lane)
