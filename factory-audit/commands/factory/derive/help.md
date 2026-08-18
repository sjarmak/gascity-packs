# gc factory derive

Read the installation and write down what it actually does.

## Usage

```bash
gc <binding> factory derive [--rewrite-probes] [--exclude <dir>]...
```

Two passes, both read-only against the city:

1. **probes-init** walks the tree, finds call sites that perform outbound
   effects (pushes, pull requests, issues, releases, images, deploys, messages,
   mail), and scaffolds `<city>/.gc/factory-audit/probes.yaml` naming where each
   one lives and which flag would carry a retry identity.
2. **infer** runs those probes and reports, per effect, whether the call sites
   carry that identity — and at which of them it is missing.

## Outputs

| File | What it is |
| --- | --- |
| `probes.yaml` | where each effect is performed, and what identity to look for |
| `factory.derived.yaml` | the contract this installation implies, as it stands |
| `evidence.json` | every call site behind every line of the derived contract |
| `derived.txt` | the same reading in prose |

## The probe pack is yours after the first run

The scaffold guesses. It finds candidate call sites by pattern and proposes the
flag that would carry an identity, and only a person can say which guesses are
right — so the file is written once and then hand-edited. Later runs keep it.
`--rewrite-probes` re-scaffolds and leaves your previous version alongside as a
`.bak`.

## The derived contract is a description, not a target

It records what the code does today, including the parts you are not happy
with. Copy the lines you agree with into your own `factory.yaml`; leave the
ones you intend to change, and let `gc factory reconcile` keep showing you the
gap until you close it.
