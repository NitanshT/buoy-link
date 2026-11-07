"""Collect local diagnostics without changing system configuration."""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

TOOLS = ("ip", "vcgencmd", "ping", "curl", "ssh", "mmcli", "nmcli")


def parse_os_release(text: str) -> Dict[str, str]:
    """Parse os-release's shell-style assignments without executing them."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                value = re.sub(r'\\([\\"$`])', r'\1', value)
        result[key] = value
    return result


def parse_ip_json(text: str) -> List[Dict[str, Any]]:
    """Validate iproute2 JSON without discarding its interface or route fields."""
    value = json.loads(text)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("expected a JSON array of objects")
    return value


def parse_temperature(text: str) -> float:
    match = re.fullmatch(r"\s*temp=(-?\d+(?:\.\d+)?)'C\s*", text)
    if not match:
        raise ValueError("unexpected temperature output")
    return float(match.group(1))


def parse_throttled(text: str) -> Dict[str, Any]:
    match = re.fullmatch(r"\s*throttled=(0x[0-9a-fA-F]+)\s*", text)
    if not match:
        raise ValueError("unexpected throttling output")
    mask = int(match.group(1), 16)
    names = {
        0: "under_voltage_now", 1: "frequency_capped_now",
        2: "throttled_now", 3: "soft_temperature_limit_now",
        16: "under_voltage_occurred", 17: "frequency_capping_occurred",
        18: "throttling_occurred", 19: "soft_temperature_limit_occurred",
    }
    return {"raw": match.group(1), "flags": {name: bool(mask & (1 << bit)) for bit, name in names.items()}}


def run_probe(args: List[str], parser) -> Dict[str, Any]:
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=5, check=True)
        return {"data": parser(completed.stdout)}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"error": str(exc)}


def collect() -> Dict[str, Any]:
    try:
        os_release = {"data": parse_os_release(Path("/etc/os-release").read_text(encoding="utf-8"))}
    except OSError as exc:
        os_release = {"error": str(exc)}
    try:
        usage = shutil.disk_usage("/")
        disk = {"data": {"path": "/", "total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}}
    except OSError as exc:
        disk = {"error": str(exc)}
    return {
        "os": {"platform": platform.platform(), "os_release": os_release},
        "interfaces": run_probe(["ip", "-j", "address", "show"], parse_ip_json),
        "routes": {
            "ipv4": run_probe(["ip", "-j", "-4", "route", "show", "table", "all"], parse_ip_json),
            "ipv6": run_probe(["ip", "-j", "-6", "route", "show", "table", "all"], parse_ip_json),
        },
        "disk": disk,
        "temperature_c": run_probe(["vcgencmd", "measure_temp"], parse_temperature),
        "throttling": run_probe(["vcgencmd", "get_throttled"], parse_throttled),
        "tools": {name: shutil.which(name) for name in TOOLS},
    }


def main() -> None:
    print(json.dumps(collect(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
