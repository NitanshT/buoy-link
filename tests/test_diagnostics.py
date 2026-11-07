import json
import subprocess

import pytest

from buoy_link import diagnostics as d


def test_os_release_parses_quotes_escapes_and_ignores_invalid_lines():
    text = '''# comment
NAME="Raspberry Pi OS"
ID=debian
PRETTY_NAME="Pi \\"Test\\""
INVALID-KEY=value
MALFORMED
'''
    assert d.parse_os_release(text) == {
        "NAME": "Raspberry Pi OS", "ID": "debian", "PRETTY_NAME": 'Pi "Test"'
    }


def test_ip_json_preserves_fields():
    data = [{"ifname": "eth0", "addr_info": [{"local": "192.0.2.1"}]}]
    assert d.parse_ip_json(json.dumps(data)) == data
    assert d.parse_ip_json("[]") == []


@pytest.mark.parametrize("text", ['{}', '[1]', 'not json'])
def test_ip_json_rejects_invalid_data(text):
    with pytest.raises(ValueError):
        d.parse_ip_json(text)


def test_temperature_parser():
    assert d.parse_temperature("temp=42.5'C\n") == 42.5
    with pytest.raises(ValueError):
        d.parse_temperature("42.5")


def test_throttling_distinguishes_current_and_historical_flags():
    result = d.parse_throttled("throttled=0x50001\n")
    assert result["flags"]["under_voltage_now"]
    assert result["flags"]["under_voltage_occurred"]
    assert result["flags"]["throttling_occurred"]
    assert not result["flags"]["throttled_now"]
    with pytest.raises(ValueError):
        d.parse_throttled("throttled=oops")


def test_probe_reports_missing_command_and_timeout(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("not installed")
    monkeypatch.setattr(d.subprocess, "run", missing)
    assert "not installed" in d.run_probe(["ip"], d.parse_ip_json)["error"]

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 5)
    monkeypatch.setattr(d.subprocess, "run", timeout)
    assert "timed out" in d.run_probe(["ip"], d.parse_ip_json)["error"]


def test_probe_reports_malformed_output(monkeypatch):
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, "bad"))
    assert "error" in d.run_probe(["ip"], d.parse_ip_json)
