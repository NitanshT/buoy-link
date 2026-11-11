"""Explicit, scoped cellular connectivity check; never changes a default route."""

import argparse
import ipaddress
import json
import signal
import subprocess
from pathlib import Path

DESTINATION = "1.1.1.1"
TABLE = "192"
PRIORITY = "5200"


class ProbeError(Exception):
    pass


def run(args, timeout=5):
    """Avoid shell execution and avoid logging subprocess output or arguments on errors."""
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"{args[0]} command failed ({type(exc).__name__})") from exc


def counters():
    base = Path('/sys/class/net/wwan0/statistics')
    return {name: int((base / (name + '_bytes')).read_text().strip()) for name in ('rx', 'tx')}


def probe(source, gateway):
    source = str(ipaddress.IPv4Address(source))
    gateway = str(ipaddress.IPv4Address(gateway))
    prefix = source + '/32'
    target = DESTINATION + '/32'
    route = ['ip', '-4', 'route', 'add', target, 'via', gateway, 'dev', 'wwan0', 'table', TABLE]
    rule = ['ip', '-4', 'rule', 'add', 'priority', PRIORITY, 'from', prefix, 'to', target, 'table', TABLE]
    rules = json.loads(run(['ip', '-j', '-4', 'rule', 'show']))
    routes = json.loads(run(['ip', '-j', '-4', 'route', 'show', 'table', 'all']))
    if any(str(item.get('priority', '')) == PRIORITY for item in rules):
        raise ProbeError('temporary rule priority is already in use')
    if any(str(item.get('table', '')) == TABLE for item in routes):
        raise ProbeError('temporary route table is already in use')
    addresses = json.loads(run(['ip', '-j', '-4', 'addr', 'show', 'dev', 'wwan0']))
    if not any(a.get('local') == source for item in addresses for a in item.get('addr_info', [])):
        raise ProbeError('source address is not assigned to wwan0')
    before = counters()
    route_attempted = False
    rule_attempted = False
    cleanup_errors = []
    try:
        # Attempt deletion even if an add times out after the kernel accepts it.
        route_attempted = True
        run(route)
        rule_attempted = True
        run(rule)
        selected = json.loads(run(['ip', '-j', '-4', 'route', 'get', DESTINATION, 'from', source]))
        if len(selected) != 1 or selected[0].get('dev') != 'wwan0' or selected[0].get('gateway') != gateway:
            raise ProbeError('route verification failed; no request sent')
        response = run(['curl', '-4', '--head', '--silent', '--show-error', '--noproxy', '*',
                        '--interface', source, '--connect-timeout', '8', '--max-time', '15',
                        '--output', '/dev/null', '--write-out', '%{http_code} %{local_ip} %{remote_ip} %{ssl_verify_result}',
                        'https://1.1.1.1/'], timeout=18).strip().split()
        if len(response) != 4 or response[1:] != [source, DESTINATION, '0']:
            raise ProbeError('unexpected HTTPS response metadata')
        return {'http_status': int(response[0]), 'tls_verified': True,
                'route': {'destination': DESTINATION, 'source': source, 'gateway': gateway, 'interface': 'wwan0'},
                'interface_bytes_before': before, 'interface_bytes_after': counters()}
    finally:
        for attempted, command in ((rule_attempted, rule), (route_attempted, route)):
            if attempted:
                try:
                    run(command[:3] + ['del'] + command[4:])
                except ProbeError as exc:
                    cleanup_errors.append(str(exc))
        if cleanup_errors:
            raise ProbeError('cleanup failed; inspect temporary rule 5200 and route table 192')


def main():
    parser = argparse.ArgumentParser(description='Opt-in bounded HTTPS check via an existing wwan0 bearer')
    parser.add_argument('--source', required=True, help='IPv4 address currently assigned to wwan0')
    parser.add_argument('--gateway', required=True, help='Gateway reported by the active cellular bearer')
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise ProbeError('interrupted')

    previous = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGHUP)}
    try:
        print(json.dumps(probe(args.source, args.gateway), indent=2))
    except (ProbeError, ValueError, OSError, KeyboardInterrupt) as exc:
        # Never include arbitrary subprocess stderr or modem/SIM identifiers.
        print(json.dumps({'error': str(exc) if isinstance(exc, ProbeError) else type(exc).__name__}))
        raise SystemExit(1)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    main()
