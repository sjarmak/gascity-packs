# gc factory audit

Run the rule catalog against the contract you maintain.

## Usage

```bash
gc <binding> factory audit [--contract <path>] [--strict]
```

Defaults to `<city>/.gc/factory-audit/factory.yaml`. Writes `audit.txt` and
`findings.json` next to it, and exits nonzero when any rule FAILs. `--strict`
also exits nonzero on WARN.

## What it cannot tell you

Audit reads only the contract. A contract asserting that every effect is
idempotent and every gate enforced scores perfectly whether or not any of that
is true, which is exactly how a reliability document becomes a liability.

`gc factory reconcile` is the half that checks the claims against the code. A
green audit over a contract nobody derived is worth nothing, so run both.
