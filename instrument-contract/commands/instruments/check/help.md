# gc instruments check

Audit this city's instruments against the mechanically checkable half of the
instrument contract.

## Usage

```bash
gc <binding> instruments check                 # the whole enabled-order population
gc <binding> instruments check bin/my-reaper   # named files
gc <binding> instruments check --changed       # every modified or staged file
gc <binding> instruments check --order reaper  # everything one order runs
```

## What the exit code means

| Code | Meaning |
| --- | --- |
| `0` | every instrument in the corpus has a test, and the positive control is protected |
| `1` | an instrument has no test at all, or the positive control failed |
| `2` | the corpus could not be fully resolved, so no clean answer exists |

Exit 2 is the one worth reading twice. An audit that examined nothing and an
audit that examined everything and found it clean must never render the same,
so a partial population is never reported as green.

## What is decided and what is only evidence

One thing is decided: whether an instrument has a sibling test. That is a
filesystem fact.

The `C1`, `C2`, `C7`, `C11` and red-case lines are keyword scans over the
instrument's own source. A scan that finds nothing prints `LOOKUP_FAILED`, not
`ABSENT`, because careful code tends to predate whatever vocabulary the scan
was built from. Read those lines; do not count them.

Six clauses cannot be checked mechanically and are printed unchecked on every
run, so that a clean result cannot be mistaken for conformance.

## Configuration

| Variable | Effect |
| --- | --- |
| `INSTRUMENT_CONTRACT_ISSUE_PREFIXES` | your tracker's ID prefixes for the red-case scan, comma separated; empty turns that spelling off |
| `INSTRUMENT_CONTRACT_CONTROL` | a protected instrument of your own to use as the positive control, instead of the shipped fixture |
| `INSTRUMENT_CONTRACT_CITY` | the city root, when neither `GC_CITY_PATH` nor `GC_CITY` is set |

Point `INSTRUMENT_CONTRACT_CONTROL` at one of your own components as soon as
you have one you would stake the tool's credibility on. A shipped fixture can
drift into being the only thing the checker is still right about.

## The convention

`docs/instrument-contract.md` in this pack carries all eleven clauses and the
incidents each one came from.
