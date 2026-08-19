# factory-audit changelog

This pack does not carry the checker; it pins one (`kit.pin`). So the entries
that matter to a city running it are the pin moves, and each one says what
changed in the kit and what a city sees differently because of it.

## Unreleased

### Pin moved to `d04ce98`

Was `4f3e7fe`. Five kit commits, and they are one change: every finding that
tells a city to go edit something now hands over the thing needed to do it.

What a city running this pack sees differently.

- `review` prints a fourth line, `at <path>`, under every finding. A derived
  contract for a repository of ordinary size runs several hundred lines and
  holds one effect block per effect, whose findings are worded identically
  apart from a name. "Decide deduplicate, converge, reconcile, or
  at_least_once" used to arrive with the reader still owing themselves a
  search. (`39e44e4`)
- `probes-init` says, per directory, how much of what it counted is prose
  rather than code, and names the directories that are entirely prose. Its own
  first question is which directories are the factory's own output, and it had
  been showing a list with no way to answer. On the repository this pack was
  written against, the second largest source was 275 finished release
  checklists, sitting next to the directory of real scripts at a nearly
  identical count and looking the same. It will never name a directory holding
  any code, which is the one exclusion that would flatter a score. (`c0e84cb`)
- EFFECT-001 says what it can support. It reads the contract and never the
  installation, so it was making a claim about the city from a field the
  contract author wrote, and it now reports the value it did observe instead
  of only asking for a different one. (`fd860d8`)
- `reconcile` prints the instruction lane, so a city whose effects are
  triggered from agent prose can see which lines those are instead of a
  count. (`c694478`)
- EFFECT-006 names `reconcile`. Its remedy is to move call sites into a
  script, and `review` holds a count and no locations: it is handed a contract
  and never an installation, so it cannot have them. The half of the tool that
  reads the installation prints the lines. (`d04ce98`)

Nothing about scoring moved, in either direction, and that is the property
tested hardest, because a reporting change that quietly improves a result is
the exact failure this checker exists to catch. On the city this pack was
written against, `review` reports the same verdicts item for item before and
after all five: the only difference in `findings.json` is the wording of the
EFFECT-006 hint.

### Pin moved to `4f3e7fe`

Was `c35aea0`. What a city running this pack sees differently: `reconcile` now
prints the matches it sets aside, under the effect they belong to and with the
matched text, the same way `derive` already did.

Why that is a pin move rather than a cosmetic one. The reason string on a
drifted effect ends "N match(es) set aside for review, exclude the ones that
are not invocations with not_regex in the probe pack", and it named none of
them. Reconcile is the command you put on a schedule and the one whose exit
code gates a build, so the instruction was reaching the reader in the one place
the evidence was missing. On the city this pack was written against, nine such
matches hold three of five effects undecided, and each is a diagnostic string
inside a fenced wrapper naming the command it wraps.

Nothing about scoring moved. A set-aside match still forces the identity to
undecided, on purpose: the shapes it cannot tell apart include a real command
assembled into a variable to run later, and a rule that dropped them would be a
guard that can only ever improve a score.

The enumeration is printed under DRIFT and OPEN and not under UNVERIFIED, which
is not an oversight: every route to UNVERIFIED excludes set-aside matches by
construction, so a call there could never fire.

### Pin moved to `c35aea0`

Was `ca66097`. What a city running this pack sees differently: an observability
promise that declares no objective is now a WARN (OBS-002 and OBS-003), a
contract may carry `observability.objectives`, and `factory_check cites`
resolves every `path:line` a contract writes about code so a citation that rots
says so instead of sitting there looking authoritative.

The pin still names a commit the published remote does not carry, so `setup`
refuses. `kit.pin` says so in the file rather than only here.

### The gc-city template scored its own tests, and lost an effect to a wrapper

Both found by running the three commands against the city the template was
written against, which is the only way either of them shows up: neither is an
error, and both move a number quietly.

`harness_globs` listed `bin/*.test` and its siblings and nothing else, so tests
living anywhere else were population. Nine of the twelve `git_push` call sites
reported as carrying no identity came from one file whose whole job is to
exercise the verb. Scoped to `**/` now, and the reading went from `12 of 19` to
`1 of 8`.

The `slack_publish` scripted matcher named the literal `gc`. Every send in that
city had moved behind a wrapper whose one real line is `"$GC_BIN" slack
publish-to-channel "${ARGS[@]}"`, which the literal does not match, so the
effect read as ZERO scripted call sites and reported as something only agents
perform. Matching the verb instead of the binary recovers it.

Naming the binary as a pattern was tried first and is wrong in a way worth
recording: the match then starts inside the opening quote of `"$GC_BIN"`, and
the quoting check correctly sets aside every wrapper line as a mention. Anchor
on the verb and the match lands after the quote closes.


### A clean audit could be printed over a contract the code contradicts

`audit` scores the contract and `reconcile` checks the contract
against the installation. Every document in the pack said so, including the
audit command's own header: *"a green audit over a contract nobody derived is
worth nothing."* Nothing enforced it. A user who ran only `gc <binding> factory
audit` got `0 FAIL, 0 WARN` and exit 0 over a contract reconcile would have
reported as DRIFT, and that number is the one that ends up quoted.

Reconcile now writes `reconcile.receipt` next to `reconcile.txt`. It records a
SHA-256 of two files, the contract and the probe pack, and records the
installation path, the kit commit and its own exit status as plain values. The scheduled `factory-drift` order writes
the same receipt, so a city that checks itself daily is not reported as
unverified.

Audit reads it and prints `verification: NONE | STALE | DRIFTED | ERRORED |
VACUOUS | CONFIRMED` above the score and again below it. `DRIFTED` exits 4
whatever the findings say. `--require-verified` extends that to `NONE`,
`STALE`, `ERRORED` and `VACUOUS` for a CI job that should refuse an unchecked
contract.

Matching is on digests rather than paths, so editing the contract after a clean
reconcile returns it to `STALE`. That is the case the mechanism exists for: the
verified state has to be lost by the edit, not carried through it.

### The verification receipt reported CONFIRMED over a contract that confirmed nothing

Found by standing the pack up in a scratch city against the real `gc` rather
than by reading it. The newcomer path -- `setup`, `derive`, copy the derived
file to `factory.yaml`, `reconcile`, `audit` -- printed:

```
0 drift, 0 unverified, 0 confirmed, 5 open (of 5 declared)
verification: CONFIRMED. Reconciled against <city>, no drift.
```

`0 drift` is not the same claim as `this contract is true`. Reconcile exits 0
when the installation contradicts nothing, and a contract that leaves every
effect undecided has nothing for a probe to contradict. So the first reconcile
anyone runs after `derive` exits 0, and reading only that exit status turns an
unchecked document into a verified one -- the pack's own failure mode wearing
its own badge.

The receipt is now `receipt_version=2` and records the reconcile counts
(`drift`, `unverified`, `confirmed`, `open`, `declared`) alongside the digests.
A version-1 receipt reads as `STALE`, and counts that cannot be parsed read as
`ERRORED`; neither produces a green. Status 0 with `confirmed=0` over a
non-empty contract is the new `VACUOUS` state, which `--require-verified`
refuses along with `NONE`, `STALE` and `ERRORED`.

### Every instruction the pack printed named a command that does not exist

`gc <binding> setup` is how a pack command is reached, and the binding
is the key under `[imports.<name>]` in the city's pack.toml. Gas City hands a
pack command `GC_PACK_NAME`, which is the PACK's name, and exposes nothing
carrying the binding. So a city that imported this pack as `[imports.fa]` ran
`gc fa audit`, was told `Run: gc factory setup`, and got `gc: unknown
command "factory"`. The two places that already tried to name it used
`GC_PACK_NAME` and were right only when an operator happened to bind the pack
under its own name.

The binding is now recovered from the city's own pack.toml, by matching the
import whose source resolves to `GC_PACK_DIR`
(`assets/scripts/gc_binding.py`). Zero or several matches print the README's
`<binding>` placeholder rather than a guess: a wrong concrete name reads as an
instruction, a placeholder does not.

That fix was verified against a real `gc` and it exposed a second defect
underneath it, which no amount of reading would have found. The commands lived
under `commands/factory/`, so the verb gc actually registered was `gc <binding>
factory audit` -- while `pack.toml`, the README, the changelog and all four
`help.md` files said `gc factory audit`. Standing the pack up in a scratch city
returned gc's root help and exit 1 for every command in it, including
`--help`. The tree is flat now: `gc <binding> audit | derive | reconcile |
setup`.

Verified against a real `gc`, not a stub. Bound as `fa`: `Run: gc fa setup`.
Bound as `factory-audit`: `Run: gc factory-audit setup`. The whole chain
(`setup`, `derive`, `audit`, `reconcile`) runs through `gc` with the pinned kit
in place and names the binding in every hint.

Error-message prefixes (`factory-audit audit: no contract at ...`) still say the
pack's own name and no longer begin with `gc`. They identify which command
failed rather than telling anyone what to type, and a prefix that reads as a
command line is an instruction whether it was meant as one or not.

### Kit pin moved to `ca66097` (from `37c873d`, 12 commits)

`docs(readme): the front page sent people to the hand-written contract`

The reason to move it: two of those commits fix things a city sees on its
*first* run, and neither could be found on the installation the kit was written
against.

- **`gc <binding> derive` printed a fix list for an identity nobody declared.**
  A scaffolded probe pack has no identity name yet, so the derived report said
  "there is nothing to look for" and then printed a `no unknown: <path>` line
  for every call site it had just found, one line per site, contradicting the
  summary directly above it. Measured on a 4,863-file installation: 116 output
  lines before, 62 after, the 54 removed being exactly those lines. The sites
  are still reported as sites. Only the claim that they are failing is
  withdrawn. (`9e51b48`)
- **The set-aside gate named a language the classifier never emits.** It
  listed `markdown`; the classifier emits `md`. A branch that can never be
  taken reads as covered, so mentions of an effect inside prose were never set
  aside from the fix list. No reading moved on the installation the kit was
  written against, because that one has no such sites. (`e1a0cad`)
- **The README's only "use it on your own factory" path was the shape the
  quickstart warns against**, sending a new user to hand-write a contract
  instead of deriving one from their installation. It now leads with
  `probes-init` then `infer` then `review`. (`ca66097`)

The rest change how much a large city has to read:

- The scan skips paths the installation's own VCS declares to be output, and
  the probe scaffold does the same, so a tree with vendored or generated
  directories no longer reports call sites inside them. (`9796b50`, `04eeaea`)
- The fix list sets aside quoted mentions, splits shell commands on separators
  outside quotes, and stops reading a bare assignment as a call. Fewer entries,
  and the ones left are call sites. (`08a6493`, `bad4d32`, `2694405`)
- `gc <binding> reconcile` compares the code lane, so a `confirmed` verdict is
  reachable at all, and a fenced call site now improves the score rather than
  reading as unfenced. (`f2643a6`, `9e1441e`)

Two documentation commits in the kit (`1391590`, `f575ff7`) do not change any
reading.

**This pin names a commit that is not yet published**, so `gc <binding> setup`
will refuse it with "the pack's pin names a commit the remote does not carry"
and check out nothing. That refusal is the designed behaviour for an unfetchable
pin, not a pack defect, and it clears when the kit commits are pushed.

## 0.1.0

First version. `gc <binding> setup` / `derive` / `audit` / `reconcile`, a daily
read-only drift order, and a probe template.
