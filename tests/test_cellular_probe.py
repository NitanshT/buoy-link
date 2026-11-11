import json

import pytest

from buoy_link import cellular_probe as p


class FakeSystem:
    def __init__(self, fail=None, wrong_route=False):
        self.calls = []
        self.fail = fail
        self.wrong_route = wrong_route

    def __call__(self, args, timeout=5):
        self.calls.append(args)
        action = ' '.join(args)
        if self.fail and self.fail in action:
            raise p.ProbeError('simulated failure')
        if args[:5] == ['ip', '-j', '-4', 'rule', 'show']:
            return '[]'
        if args[:5] == ['ip', '-j', '-4', 'route', 'show']:
            return '[]'
        if args[:5] == ['ip', '-j', '-4', 'addr', 'show']:
            return json.dumps([{'addr_info': [{'local': '10.0.0.2'}]}])
        if args[:5] == ['ip', '-j', '-4', 'route', 'get']:
            return json.dumps([{'dev': 'tailscale0' if self.wrong_route else 'wwan0', 'gateway': '10.0.0.1'}])
        if args[0] == 'curl':
            return '301 10.0.0.2 1.1.1.1 0'
        return ''


def setup(monkeypatch, **kwargs):
    fake = FakeSystem(**kwargs)
    monkeypatch.setattr(p, 'run', fake)
    monkeypatch.setattr(p, 'counters', lambda: {'rx': 0, 'tx': 0})
    return fake


def mutations(fake):
    return [' '.join(c) for c in fake.calls if c[0] == 'ip' and len(c) > 3 and c[3] in ('add', 'del')]


def test_probe_verifies_route_and_cleans_rule_before_route(monkeypatch):
    fake = setup(monkeypatch)
    result = p.probe('10.0.0.2', '10.0.0.1')
    assert result['http_status'] == 301 and result['tls_verified']
    assert mutations(fake) == [
        'ip -4 route add 1.1.1.1/32 via 10.0.0.1 dev wwan0 table 192',
        'ip -4 rule add priority 5200 from 10.0.0.2/32 to 1.1.1.1/32 table 192',
        'ip -4 rule del priority 5200 from 10.0.0.2/32 to 1.1.1.1/32 table 192',
        'ip -4 route del 1.1.1.1/32 via 10.0.0.1 dev wwan0 table 192',
    ]
    assert next(i for i, c in enumerate(fake.calls) if c[0] == 'curl') > next(i for i, c in enumerate(fake.calls) if c[:5] == ['ip', '-j', '-4', 'route', 'get'])


@pytest.mark.parametrize('fail', ['rule add', 'route get', 'curl'])
def test_cleanup_after_failure(monkeypatch, fail):
    fake = setup(monkeypatch, fail=fail)
    with pytest.raises(p.ProbeError):
        p.probe('10.0.0.2', '10.0.0.1')
    assert any('rule del' in c for c in mutations(fake))
    assert any('route del' in c for c in mutations(fake))


def test_wrong_route_never_sends_request_and_cleans_up(monkeypatch):
    fake = setup(monkeypatch, wrong_route=True)
    with pytest.raises(p.ProbeError, match='route verification'):
        p.probe('10.0.0.2', '10.0.0.1')
    assert not any(c[0] == 'curl' for c in fake.calls)
    assert 'route del' in mutations(fake)[-1]


def test_route_add_failure_still_attempts_cleanup(monkeypatch):
    fake = setup(monkeypatch, fail='route add')
    with pytest.raises(p.ProbeError):
        p.probe('10.0.0.2', '10.0.0.1')
    assert any('route del' in c for c in mutations(fake))
    assert not any(c[0] == 'curl' for c in fake.calls)


def test_cleanup_failure_still_removes_route_and_is_reported(monkeypatch):
    fake = setup(monkeypatch, fail='rule del')
    with pytest.raises(p.ProbeError, match='cleanup failed'):
        p.probe('10.0.0.2', '10.0.0.1')
    assert 'route del' in mutations(fake)[-1]


def test_collision_does_not_mutate(monkeypatch):
    fake = setup(monkeypatch)
    def collision(args, timeout=5):
        if args[:5] == ['ip', '-j', '-4', 'rule', 'show']:
            return '[{"priority": 5200}]'
        return fake(args, timeout)
    monkeypatch.setattr(p, 'run', collision)
    with pytest.raises(p.ProbeError, match='already in use'):
        p.probe('10.0.0.2', '10.0.0.1')
    assert not mutations(fake)


def test_interruption_cleans_up_and_propagates(monkeypatch):
    fake = setup(monkeypatch)
    def interrupt(args, timeout=5):
        if args[0] == 'curl':
            raise KeyboardInterrupt()
        return fake(args, timeout)
    monkeypatch.setattr(p, 'run', interrupt)
    with pytest.raises(KeyboardInterrupt):
        p.probe('10.0.0.2', '10.0.0.1')
    assert 'rule del' in mutations(fake)[-2]
    assert 'route del' in mutations(fake)[-1]


def test_subprocess_errors_do_not_expose_stderr(monkeypatch):
    import subprocess
    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr='IMEI 123456789012345')
    monkeypatch.setattr(p.subprocess, 'run', failure)
    with pytest.raises(p.ProbeError) as error:
        p.run(['ip', 'route'])
    assert '123456789012345' not in str(error.value)
