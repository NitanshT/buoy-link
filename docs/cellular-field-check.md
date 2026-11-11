# CMHK cellular field check — 2026-11-11

On the Raspberry Pi 5, the Quectel RM520N-GL recognized SIM slot 1 and registered on its home CMHK network. The QMI bearer was connected. One HTTPS HEAD request to 1.1.1.1 was routed through `wwan0`, returned HTTP 301, and passed TLS certificate verification. `wwan0` interface counters increased from 0 to 4,854 bytes received and from 0 to 2,778 bytes transmitted. These are interface counters and can include other traffic; bearer byte counters were unavailable before the request.

A temporary source- and destination-specific policy rule selected the cellular gateway for the test. After cleanup, the normal lookup again selected the Tailscale exit-node table, and the Wi-Fi default route and existing Tailscale routes and rules remained unchanged. SSH stayed connected. Throughput, latency, reconnection, and Tailscale-over-cellular were not tested.

This records a single observation, not a guarantee of future connectivity. Modem and SIM identifiers are intentionally omitted.
