# Architecture

## Current scope

The `buoy-diagnostics` CLI gathers a point-in-time local inventory and emits JSON. It reads OS metadata and filesystem capacity, invokes `ip` for interface and route data, invokes `vcgencmd` for Raspberry Pi temperature and throttling, and checks whether selected diagnostic tools are on PATH. Each optional probe reports its own error when unavailable, so one failure does not prevent the remaining inventory. Command execution uses fixed arguments, no shell, and a timeout.

```text
operator -> diagnostics CLI -> local read-only probes -> JSON on stdout
```

The output is an observation, not a health verdict. Network addresses and system details may be sensitive. No data is transmitted by this command.

## Boundaries and open decisions

Modem configuration, persistent route changes, communications protocols, deployment, and remote access are outside the current implementation. The fish and any cameras are not assumed to have particular interfaces. Hardware, message formats, topology, security, and operational requirements need to be established before implementing communications. Do not commit credentials or machine-specific secrets.

## Opt-in cellular probe

`buoy-cellular-probe` is a separate, operator-invoked command, not part of the read-only inventory. It requires an already connected `wwan0` bearer; it can discover the single connected bearer or accept an explicit source and gateway. It uses an isolated routing table and a source/destination-specific temporary policy rule to verify and make one bounded HTTPS HEAD request; it attempts cleanup even when a step fails. It refuses collisions and does not alter default routes or modem configuration. Uncatchable termination or cleanup failure may leave temporary state requiring manual inspection.
