# factory-audit

Check what your city claims about its outbound effects against what its code
actually does.

## What it found in the city that wrote it

Our own installation, which has more orders, formulas and reapers than anything
we would be advising, reads:

```
5 drift, 0 unverified, 0 confirmed, 0 open (of 5 declared)
5 effect(s) the scan measured and the contract does not record
4 FAIL, 5 WARN
verification: DRIFTED
```

Nothing we declare about our own outbound effects survives contact with our own
call sites, and the `4 FAIL` is a score over a document the code contradicts, so
the audit exits nonzero whatever the rule catalog thinks of the prose.

The specific things it surfaced, each one checkable:

- **A squash merge that could lie about itself.** The merge path recorded a
  commit that was not the one the forge produced, so a retry had no way to tell
  a completed merge from an unstarted one. Fenced afterwards.
- **28 of 30 agent-nudge call sites carry no `nudge_id`.** The contract said
  they all did. Every nudge redelivery in this city is free to run finished work
  a second time, and one of them did, three times in a day.
- **1 of 8 `git push` call sites carries no expected remote ref, and 34 more
  sites are agent instructions.** The scripted lane is nearly closed. The lane
  that is not closed is the one where a prompt tells an agent to push, which no
  static check can bind, and which outnumbers the scripted sites four to one.
- **An effect that moved behind a wrapper stopped being counted at all.** Our
  Slack sends were routed through one fenced wrapper, and the probe pack still
  named the bare verb. The reading went to zero scripted call sites for an
  effect this city performs every day, and reported the effect as something only
  agents do. It is not an error state and nothing goes red: a probe pack rots
  when the code it points at moves, and the symptom is a count that quietly
  falls. The shipped `gc-city` template matches the verb rather than the binary
  because of this. If you route an effect through a wrapper of your own, add it
  to your probe pack, because nothing here can guess it.
- **Two effects are one error message away from a clean verdict, and the tool
  would not tell us which one.** `open_pull_request` and `merge_pull_request`
  both read "every readable code call site carries it; 1 match(es) set aside
  for review". The one set-aside match in each is a `printf` line inside the
  fenced wrapper for the command it wraps, naming that command in its own error
  text. A scanner cannot tell that from `PUSH_CMD="git push origin main"`, a
  real command built to run later, so it refuses to decide, which is the right
  refusal. What was wrong is that `reconcile` said "exclude the ones that are
  not invocations" and named none of them, while `derive` printed them all.
  Reconcile is the command you run on a schedule and the one whose exit code
  gates, so the instruction reached the reader without the evidence. It
  enumerates them now. Nine such matches hold three of our five effects
  undecided, and every one of the nine is a diagnostic string in a wrapper,
  which is the ordinary shape of a well-built city rather than an edge case.
- **Four effects this city performs on the outside world with nothing written
  down about half-success**, found because reconcile reported them as
  UNDECLARED against a contract their authors believed was complete.

We have not finished fixing these. That is the point of publishing the number:
a factory with this much machinery still fails its own check, so the check is
not a formality you pass by having good practices.

That reading is from 2026-08-19, and it is a reading rather than a fact about
us: it moves whenever our code or our contract does. Reproduce it, or refute it,
with the three commands this pack ships:

```bash
gc <binding> derive --template gc-city
gc <binding> reconcile --contract <your contract>
gc <binding> audit --contract <your contract>
```

Ours ran against the city's own hand-written contract with the kit at
`c35aea0`, and the drift lines name nine matches set aside as mentions rather
than invocations, which we have not settled. Settling them can only move the
reading in one direction, and we have not earned it yet.

## The two halves, and why one alone is worthless

```bash
gc <binding> audit        # reads your contract
gc <binding> reconcile    # reads your code
```

`audit` runs a rule catalog over the contract you maintain. It cannot tell
whether the contract is true. A document asserting that every effect is
idempotent and every gate enforced scores perfectly, which is exactly how a
reliability document becomes a liability.

`reconcile` runs probes against the real tree and reports where the contract
and the call sites disagree. This is the half that can catch you lying to
yourself, and the half a hand-written contract will never give you.

The first version of this had only the first half. Editing the contract to a
value we had decided on turned findings green and fixed nothing, and the score
moved by one when we declared four previously invisible effects and by zero
when we shipped the real merge fence. A checker that reads only a declaration
measures your prose.

So `audit` will not print a bare score. `reconcile` leaves a receipt recording
the SHA-256 of the contract and probe pack it read and what it found, and every
audit states, above the number and again below it, one of `NONE`, `STALE`,
`DRIFTED`, `ERRORED`, `VACUOUS` or `CONFIRMED`. A contract the last reconcile
contradicted exits 4 however clean the rules are, and editing the contract
afterwards returns it to `STALE` rather than carrying the confirmation through
the edit. Run `gc <binding> audit --require-verified` in CI to refuse an
unchecked contract outright.

`VACUOUS` is the state that caught us. Reconcile exits 0 when the installation
contradicts nothing, and a contract whose effects are all undecided asserts
nothing to contradict, so a fresh derive reconciles clean and confirms nothing.
The receipt carries the counts, so `0 drift` and `0 confirmed` are reported as
what they are instead of collapsing into a green.

## Getting a contract without writing one

```bash
gc <binding> setup     # clone the pinned checker into the city, once
gc <binding> derive    # read the installation, write what it does
cp .gc/factory-audit/factory.derived.yaml .gc/factory-audit/factory.yaml
```

`derive` walks your tree, finds the call sites that perform outbound effects,
and reports per effect whether they carry an identity a retry could dedupe on.
The derived file records what the code does **today**, including the parts you
are not happy with. Edit it into what you are willing to stand behind, and let
`reconcile` keep showing you the gap until you close it.

Nobody is going to hand-author a contract to try a tool. That is the design
constraint the whole pack is built around.

`derive` needs to know which call sites in your tree are the outbound effects.
That part is per-installation, and the pack ships one starting point:

```bash
gc <binding> derive --template gc-city
```

`gc-city` describes a Gas City built the way ours is: `gc slack`, `git push`,
`gh pr create`, `gh pr merge`, `gc session nudge`. It is not a guess about what
such a city looks like. It is the probe pack we corrected against a real one,
finding each pattern by reading the call sites it missed. Copy it, run `derive`,
read the site counts, and fix the patterns that are obviously wrong for your
tree before you trust a single number out of it. A probe pack that matches
nothing reports a clean factory.

`--template` refuses to overwrite an existing `probes.yaml`; pass
`--rewrite-probes` when you mean to discard your edits.

## A contract that already has the answers in it

`derive` leaves `effect_identity`, `retry_contract` and `unknown_state_policy`
reading `unknown` for every effect, because those are decisions and no scan can
read a decision. That is where most people stop, since a file of `unknown` shows
nothing of what a decided field is supposed to look like.

`examples/gc-city/factory.yaml` is the real contract for the city this pack was
written against, 1,171 lines, with each decision recorded next to the code
property it asserts and the command that would refute it. It ships with its nine
failures left in, because a contract you can copy is worth less than one you can
argue with, and because our own factory has not cleared them either.

Do not copy its values into yours. Declaring `deduplicate` for an effect whose
code does not deduplicate produces a green line over a broken mechanism, which
is the failure this checker exists to catch. Read the reasoning, run the
equivalent check against your tree, write your own answer.
`examples/gc-city/README.md` names every one of those failures and why it is
still open.

## What it can and cannot bind

Three kinds of call site, and the distinction is the difference between a
report you can trust and one you cannot:

| Kind | What it is | Counted? |
| --- | --- | --- |
| scripted | a line of code a static check can read | yes, and identity is checked |
| instructed | a sentence in a formula or prompt telling an agent to do it | reported, never counted as carrying an identity |
| harness | test and checker code | subtracted, but printed |

An instructed site has no argv until runtime, so no matcher can bind it. It
withdraws the identity rather than being ignored, because the errors are not
symmetric: a **missed** call site confirms an identity that does not hold, and
a **spurious** one withdraws an identity that might have held. The matcher is
allowed to err only in the second direction, and every judgment call in it
went that way.

That is also why `open` is a verdict rather than a failure. Some effects have
no identity to look for because nobody decided what one would be; reporting
that as a failed search is a false reading, since the search had no target.

## The checker is pinned, not vendored

`kit.pin` names a repository and a commit. `gc <binding> setup` clones it into
`<city>/.gc/factory-kit` and checks out that exact commit.

Copying the checker into the pack would put a second copy in every city that
installs it, and those copies drift from the one being maintained, quietly. A
pin goes stale loudly: every command prints the commit it ran and prints a
`DRIFT` line when that is not the pinned one.

`setup` is the only command that writes outside the report directory or reaches
the network. Everything else fails with an instruction when the kit is missing,
so the scheduled order can never pull code onto the machine on its own. Set
`FACTORY_KIT_HOME` to use a checkout you already have.

## The order

`orders/factory-drift.toml` reconciles once a day and goes actionable only when
the contract has gone out of date with the code. It is deliberately not the
audit: audit reads the contract alone, so a scheduled version reports the same
findings every run until someone edits a document, which is a reminder rather
than a check. Reconcile's result changes when the code changes.

It posts nothing, files nothing, and pushes nothing.

## Install

1. Add the pack to `city.toml`.
2. `gc <binding> setup`
3. `gc <binding> derive --template gc-city`, then read the probe
   pack it installed and correct it for your tree.
4. Copy the derived contract to `factory.yaml` and edit it.
5. `gc supervisor reload`
