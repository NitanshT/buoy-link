# Buoy Link

A starting point for the HKUST robotic-fish buoy communications project. The current implementation only collects local, read-only diagnostics; communication hardware and protocols remain to be defined.

## Diagnostics

On a Raspberry Pi running Linux, with Python 3.9 or newer:

```sh
python -m pip install .
buoy-diagnostics
```

The command prints JSON containing OS information, network interfaces and routes, root filesystem space, Raspberry Pi temperature and throttling status, and the availability of selected tools. Missing commands, unsupported platforms, and failed probes are reported in the output. It does not change system configuration. Inspect output before sharing it: network addresses and system details may be sensitive.

For development, install `python -m pip install -e ".[test]"` and run `python -m pytest`.

See [architecture](docs/architecture.md) for boundaries and open decisions.
