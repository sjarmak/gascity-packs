# instrument-contract

Check that your city's own instruments are capable of going red.

## What it found in the city that wrote it

That city runs 82 enabled local orders, resolving to 79 unique executables.
Reading from 2026-08-17:

```
RESULT: 8 of 79 instrument(s) have NO test at all.
UNRESOLVED: 1 instrument(s) have a test this tool could not classify.
COVERAGE: PARTIAL — 2 order binding/subject(s) could not be examined.
POSITIVE CONTROL: protected
```

Eight scheduled instruments, each one reporting into a fleet that acts on what
it says, had never been shown capable of reporting the failure they exist to
catch. Nobody skipped a step: every one of them was written carefully, ran
daily, and printed a clean line. A clean line is what an instrument that has
stopped looking prints too.

The reading exits 2, not 1, because two of the targets could not be examined at
all. A partial population is never green here: "examined everything and found
eight" and "examined most of it and found eight" are different claims, and only
one of them is about your city.

That is a reading rather than a fact about us; it moves whenever our orders or
our tests move. The way to check it is to run the same command against your own
city and see whether a number that uncomfortable is hard to get.

## What it decides, and what it refuses to decide

Exactly one thing is decided: does an instrument have a sibling test at all.
That is a filesystem fact, and it is the whole of the pass/fail.

Everything else is printed as evidence with the scan that produced it. A scan
that finds nothing prints `LOOKUP_FAILED`, never `ABSENT`. The distinction is
the reason this pack exists rather than a nicety: the first version of the
checker did report absence, and the component it called untested was the one
component in the city that had implemented the absent-versus-unknown rule
before the convention was written. It was marked in that codebase's own words,
citing the incident IDs its suite reproduces, and the grep was looking for an
imported vocabulary. A naming heuristic run over careful code reports the
careful code as the offender.

Six clauses of the contract cannot be checked mechanically at all. They are
named and printed as unchecked on every run, so a clean result can never be
read as "this conforms".

## Where the population comes from

Your enabled orders, and nothing hand-declared. The checker asks `gc order
list` what is live, resolves each order's exec down to the files it actually
runs — through `sh -c` wrappers, environment prefixes, sequential commands and
`exec` — and audits those.

It also reads `git ls-files orders/*.toml` and reports the drift both ways:
orders that are live but untracked, and orders that are tracked but not live.
A city whose scheduler and whose repository disagree is a city where the answer
to "what runs here" depends on who you ask.

An exec it cannot fully resolve makes the run partial rather than dropping the
part it could not see.

## The two controls

A checker whose only failure mode is silence can be broken into permanent
silence and still look clean. So every standing run re-checks both rails:

- `assets/fixtures/protected-canary` is a real instrument with a red-case test.
  If this tool ever calls it unprotected, the tool is wrong and its other
  answers are worthless. The run fails on that alone.
- `assets/fixtures/unprotected-canary` has no test, on purpose. It is what
  keeps the finding rail provable.

Point `INSTRUMENT_CONTRACT_CONTROL` at one of your own components as soon as
you have one you would stake the tool's credibility on. A real instrument is a
better control than a fixture, because a fixture can drift into being the only
thing the tool is still right about.

## Your vocabulary, not ours

`INSTRUMENT_CONTRACT_ISSUE_PREFIXES` holds your tracker's ID prefixes, used to
recognise a test that names the incident it reproduces. It ships with the
originating city's prefixes as a default, which are wrong for you.

```
INSTRUMENT_CONTRACT_ISSUE_PREFIXES=proj,inc,sec
```

Shipping a vocabulary as a constant would do to your careful code exactly what
it did to ours.

## Exit codes

```
0   every examined instrument has a test, and the corpus was complete
1   at least one instrument has no test, or the positive control failed
2   the corpus could not be fully resolved, or was empty
```

Three outcomes, not two. A wrapper that folds 2 into 1 reports a finding your
city does not have; one that folds it into 0 reports a clean run over a corpus
it never read. An empty corpus is a 2 for the same reason: "examined nothing"
and "examined everything and found it clean" must not render identically.

## The order

`orders/instrument-contract-audit.toml` runs the population audit daily. It is
read-only, posts nothing, and goes actionable when an instrument in your live
schedule has no test or the population stops resolving.

## Install

1. Add the pack to `city.toml`.
2. `gc <binding> instruments check` — audits the whole enabled-order
   population. With paths, it audits exactly those files, which is what you
   want in a pre-commit or on a branch.
3. Set `INSTRUMENT_CONTRACT_ISSUE_PREFIXES` for your tracker.
4. Point `INSTRUMENT_CONTRACT_CONTROL` at one of your own protected
   instruments.
5. `gc supervisor reload` to pick up the daily order.
