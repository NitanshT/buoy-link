# Architecture

## Current scope

The `buoy-diagnostics` CLI gathers a point-in-time local inventory and emits JSON. It reads OS metadata and filesystem capacity, invokes `ip` for interface and route data, invokes `vcgencmd` for Raspberry Pi temperature and throttling, and checks whether selected diagnostic tools are on PATH. Each optional probe reports its own error when unavailable, so one failure does not prevent the remaining inventory. Command execution uses fixed arguments, no shell, and a timeout.

```text
operator -> diagnostics CLI -> local read-only probes -> JSON on stdout
```

The output is an observation, not a health verdict. Network addresses and system details may be sensitive. No data is transmitted by this command.

## Boundaries and open decisions

Modem configuration, route changes, communications protocols, deployment, and remote access are outside the current implementation. The fish and any cameras are not assumed to have particular interfaces. Hardware, message formats, topology, security, and operational requirements need to be established before implementing communications. Do not commit credentials or machine-specific secrets.
