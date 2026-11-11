# Buoy Link

A starting point for the HKUST robotic-fish buoy communications project. It provides read-only diagnostics and a separate opt-in cellular connectivity check; communications protocols remain to be defined.

## Diagnostics

On a Raspberry Pi running Linux, with Python 3.9 or newer, from the project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/buoy-diagnostics
.venv/bin/buoy-cellular-probe --help
```

The command prints JSON containing OS information, network interfaces and routes, root filesystem space, Raspberry Pi temperature and throttling status, and the availability of selected tools. Missing commands, unsupported platforms, and failed probes are reported in the output. It does not change system configuration. Inspect output before sharing it: network addresses and system details may be sensitive.

For development, install `.venv/bin/python -m pip install -e ".[test]"` and run `.venv/bin/python -m pytest`.

See [architecture](docs/architecture.md) for boundaries and open decisions.

## Optional cellular check

The separate `buoy-cellular-probe` command is **disabled by default**. With an existing connected IPv4 bearer on `wwan0`, run as root using the virtual environment's executable:

```sh
sudo .venv/bin/buoy-cellular-probe --auto
```

`--auto` discovers the single connected bearer via ModemManager and checks its address, prefix, and gateway against `wwan0`; missing, inconsistent, or multiple connected bearers cause an error. Alternatively, specify `--source CELLULAR_IPV4 --gateway CELLULAR_GATEWAY`. The tool installs a temporary rule scoped to that source and `1.1.1.1`, verifies the selected gateway and interface, and sends one time-limited HTTPS HEAD request. HTTP 2xx and 3xx responses with valid TLS count as success. It removes its rule and route on normal exit, errors, interruption, and SIGTERM/SIGHUP. A forced kill or loss of power can prevent cleanup; if cleanup is reported as failed, inspect rule priority 5200 and routing table 192. The tool refuses to run if either is already in use. It does not configure a modem, APN, or default route. Output includes network addresses but no SIM or modem identifiers.

See the [CMHK field check](docs/cellular-field-check.md) for the observed result and limits.
