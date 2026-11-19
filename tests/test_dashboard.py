import json

from buoy_link import dashboard as d


def test_modem_registration_does_not_imply_connected(monkeypatch):
    def fake(args):
        if args[1] == '-L':
            return {'modem-list': ['/org/freedesktop/ModemManager1/Modem/7']}
        if args[1] == '-m':
            return {'modem': {'generic': {'access-technologies': ['lte'], 'signal-quality': {'value': '80', 'recent': 'yes'}, 'bearers': ['/org/freedesktop/ModemManager1/Bearer/3']}, '3gpp': {'registration-state': 'home'}}}
        return {'bearer': {'status': {'connected': 'no'}}}
    monkeypatch.setattr(d, 'json_command', fake)
    value = d.modem_status()
    assert value['registration'] == 'home'
    assert value['bearer'] == 'disconnected'
    assert value['signal'] == '80%'


def test_missing_modem_and_multiple_modems_are_unavailable(monkeypatch):
    for listing in (None, {'modem-list': []}, {'modem-list': ['a', 'b']}):
        monkeypatch.setattr(d, 'json_command', lambda args: listing)
        assert d.modem_status()['bearer'] == 'unavailable'


def test_preferred_route_uses_main_route_metric(monkeypatch):
    monkeypatch.setattr(d, 'json_command', lambda args: [{'dev': 'wwan0', 'metric': 900}, {'dev': 'wlan0', 'metric': 600}])
    assert d.preferred_route() == 'Wi-Fi'


def test_recorded_probe_requires_timestamp_and_valid_tls(tmp_path):
    path = tmp_path / 'probe.json'
    path.write_text(json.dumps({'http_status': 301, 'tls_verified': True}), encoding='utf-8')
    assert d.recorded_probe(path) == 'Unavailable or incomplete'
    path.write_text(json.dumps({'http_status': 301, 'tls_verified': True, 'recorded_at': '2026-11-19T10:00:00Z'}), encoding='utf-8')
    assert 'HTTP 301' in d.recorded_probe(path)


def test_journal_messages_are_never_rendered(monkeypatch):
    line = json.dumps({'_SYSTEMD_UNIT': 'ModemManager.service', '__REALTIME_TIMESTAMP': '1795070000000000', 'MESSAGE': 'IMEI 123456789012345 secret password'})
    monkeypatch.setattr(d, 'command', lambda args: line)
    events = d.recent_events()
    assert '123456789012345' not in str(events)
    assert 'password' not in str(events)


def test_render_escapes_untrusted_values():
    data = {'updated': 'now', 'summary': '<script>alert(1)</script>', 'detail': 'detail', 'uptime': '1m', 'temperature': '20', 'wifi': 'connected', 'modem': {'bearer': 'disconnected', 'registration': 'home', 'technology': 'lte', 'signal': '80%'}, 'route': 'Wi-Fi', 'tailscale': 'Running', 'clock': 'unknown', 'probe': 'Not recorded', 'events': [('now', '<img src=x>')]}
    page = d.render(data)
    assert '<script>' not in page and '<img src=x>' not in page
    assert '&lt;script&gt;' in page and '&lt;img src=x&gt;' in page
