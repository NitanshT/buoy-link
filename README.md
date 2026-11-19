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

## Status dashboard

Start the dashboard on the Pi from the project directory:

```sh
.venv/bin/buoy-dashboard
```

It listens only on `127.0.0.1:8765`. On Windows, with SSH key authentication already working, pass the Pi's reachable SSH destination explicitly in PowerShell from your checkout. For Wi-Fi:

```powershell
./scripts/open-dashboard.ps1 -Pi pi@10.79.8.214
```

Alternatively, if Tailscale is connected, use `./scripts/open-dashboard.ps1 -Pi pi@100.68.26.99`. Use the Pi's current address if it has changed; the launcher does not require an SSH alias or Tailscale when using Wi-Fi. It opens a local SSH tunnel and starts the browser. Keep its PowerShell window open; press Enter to close the tunnel. Use `-LocalPort 8766` if needed. If the page is unavailable, start the Pi dashboard first. The Pi service must remain running independently of the tunnel.

The dashboard is read-only and does not initiate a cellular probe. An optional existing probe JSON file can be supplied with `--probe-result PATH`; it must include an ISO 8601 `recorded_at`, `http_status`, and `tls_verified`. Without such a file it reports “Not recorded.” Event details are deliberately withheld because journals can contain identifiers. A registered modem is not necessarily data-connected. Cellular-only Tailscale SSH has not passed testing; do not rely on it for remote access.

## Optional cellular check

The separate `buoy-cellular-probe` command is **disabled by default**. With an existing connected IPv4 bearer on `wwan0`, run as root using the virtual environment's executable:

```sh
sudo .venv/bin/buoy-cellular-probe --auto
```

`--auto` discovers the single connected bearer via ModemManager and checks its address, prefix, and gateway against `wwan0`; missing, inconsistent, or multiple connected bearers cause an error. Alternatively, specify `--source CELLULAR_IPV4 --gateway CELLULAR_GATEWAY`. The tool installs a temporary rule scoped to that source and `1.1.1.1`, verifies the selected gateway and interface, and sends one time-limited HTTPS HEAD request. HTTP 2xx and 3xx responses with valid TLS count as success. It removes its rule and route on normal exit, errors, interruption, and SIGTERM/SIGHUP. A forced kill or loss of power can prevent cleanup; if cleanup is reported as failed, inspect rule priority 5200 and routing table 192. The tool refuses to run if either is already in use. It does not configure a modem, APN, or default route. Output includes network addresses but no SIM or modem identifiers.

See the [CMHK field check](docs/cellular-field-check.md) for the observed result and limits.
