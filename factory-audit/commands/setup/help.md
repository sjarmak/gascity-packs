# gc <binding> setup

Clone the pinned reliability kit into the city, once.

## Usage

```bash
gc <binding> setup [--force]
```

Reads `kit.pin` from the pack, clones that repository into
`<city>/.gc/factory-kit`, and checks out that exact commit. If the checkout
already exists at the pinned commit it does nothing.

`--force` fetches and re-checks-out the pin over an existing checkout at some
other commit.

## Why the kit is not inside the pack

Vendoring the checker would put a second copy of it in every city that installs
this pack, and those copies drift from the one being maintained. A pin can also
go stale, but it says so: `audit`, `derive`, and `reconcile` each print
the commit they ran, and print a `DRIFT` line when it is not the pinned one.

## The only command here that writes outside the report directory

Setup is the only network access and the only install in the pack. Every other
command fails with an instruction when the kit is absent, so the scheduled
order can never pull code onto the machine by itself.

To point the pack at a checkout you already have, set `FACTORY_KIT_HOME` to its
root and skip setup entirely.
