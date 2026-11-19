"""Loopback-only read-only buoy status dashboard."""
import argparse
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .diagnostics import parse_temperature


def command(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=4, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def json_command(args):
    try:
        return json.loads(command(args) or 'null')
    except (ValueError, TypeError):
        return None


def modem_status():
    result = dict(registration='unavailable', technology='unavailable', signal='unavailable', bearer='unavailable')
    listing = json_command(['mmcli', '-L', '-J'])
    modems = listing.get('modem-list', []) if isinstance(listing, dict) else []
    if not isinstance(modems, list) or len(modems) != 1 or not isinstance(modems[0], str) or not re.fullmatch(r'/org/freedesktop/ModemManager1/Modem/\d+', modems[0]):
        return result
    try:
        item = json_command(['mmcli', '-m', modems[0], '-J'])['modem']
        generic = item['generic']
        registration = item['3gpp'].get('registration-state')
        if registration in ('home', 'roaming', 'searching', 'idle', 'denied', 'unknown'):
            result['registration'] = registration
        tech = generic.get('access-technologies')
        if isinstance(tech, list):
            result['technology'] = ', '.join(x for x in tech if x in ('lte', '5gnr', 'umts', 'gsm', 'edge')) or 'unavailable'
        quality = generic.get('signal-quality', {})
        if str(quality.get('value', '')).isdigit() and 0 <= int(quality['value']) <= 100:
            result['signal'] = str(quality['value']) + '%' + ('' if quality.get('recent') in ('yes', True) else ' (cached)')
        paths = generic.get('bearers') or []
        if len(paths) == 1 and re.fullmatch(r'/org/freedesktop/ModemManager1/Bearer/\d+', paths[0]):
            state = json_command(['mmcli', '-b', paths[0], '-J'])['bearer']['status']['connected']
            result['bearer'] = {'yes': 'connected', 'no': 'disconnected'}.get(state, 'unavailable')
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        pass
    return result


def connection_state(device):
    value = command(['nmcli', '-t', '-f', 'GENERAL.STATE', 'device', 'show', device]) or ''
    match = re.match(r'(\d+)', value.partition(':')[2].strip())
    if not match:
        return 'unavailable'
    state = int(match.group(1))
    return 'connected' if state == 100 else ('disconnected' if state in (20, 30, 120) else 'connecting')


def preferred_route():
    routes = json_command(['ip', '-j', '-4', 'route', 'show', 'table', 'main', 'default'])
    try:
        route = min(routes, key=lambda item: int(item.get('metric', 0)))
        return {'wlan0': 'Wi-Fi', 'wwan0': 'Cellular'}.get(route.get('dev'), 'Other interface')
    except (TypeError, ValueError, AttributeError):
        return 'unavailable'


def recorded_probe(path):
    if not path:
        return 'Not recorded'
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        status, timestamp = data.get('http_status'), data.get('recorded_at')
        if not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599 or data.get('tls_verified') is not True or not isinstance(timestamp, str):
            return 'Unavailable or incomplete'
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return f'HTTP {status} · TLS verified · {timestamp}'
    except (OSError, ValueError, TypeError, AttributeError):
        return 'Unavailable or incomplete'


def recent_events():
    raw = command(['journalctl', '-u', 'NetworkManager', '-u', 'ModemManager', '-u', 'tailscaled', '-p', 'warning', '-n', '12', '-o', 'json', '--no-pager'])
    if raw is None:
        return [('Unavailable', 'Recent events are unavailable to this user.')]
    events = []
    for line in raw.splitlines():
        try:
            data = json.loads(line)
            unit = data.get('_SYSTEMD_UNIT', '')
            if unit not in ('NetworkManager.service', 'ModemManager.service', 'tailscaled.service'):
                continue
            stamp = datetime.fromtimestamp(int(data['__REALTIME_TIMESTAMP']) / 1000000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            message = data.get('MESSAGE', '')
            message = message.lower() if isinstance(message, str) else ''
            if 'network reject' in message or 'network-failure' in message:
                label = 'Mobile network rejection or failure'
            elif 'dns' in message:
                label = 'DNS warning or error'
            elif 'timed out' in message or 'timeout' in message:
                label = 'Operation timed out'
            elif 'failed' in message or 'error' in message:
                label = 'Operation failed'
            else:
                label = 'Warning or error'
            events.append((stamp, unit.removesuffix('.service') + ': ' + label + '.'))
        except (ValueError, TypeError, KeyError, OSError, OverflowError):
            continue
    return events or [('No recent events', 'No warnings or errors were returned.')]


def collect_status(probe_path=None):
    try:
        seconds = int(float(Path('/proc/uptime').read_text().split()[0]))
        uptime = f'{seconds // 86400}d {(seconds % 86400) // 3600}h {(seconds % 3600) // 60}m'
    except (OSError, ValueError, IndexError):
        uptime = 'unavailable'
    try:
        temperature = f'{parse_temperature(command(["vcgencmd", "measure_temp"]) or ""):g} °C'
    except ValueError:
        temperature = 'unavailable'
    sync = (command(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value']) or '').strip()
    clock = {'yes': 'synchronized', 'no': 'not synchronized'}.get(sync, 'unavailable')
    ts_data = json_command(['tailscale', 'status', '--json'])
    state = ts_data.get('BackendState') if isinstance(ts_data, dict) else None
    ts = state if state in ('Running', 'Stopped', 'Starting', 'NeedsLogin', 'NeedsMachineAuth') else 'unavailable'
    if isinstance(ts_data, dict) and ts_data.get('Health'):
        ts += ' · health warning'
    wifi, modem = connection_state('wlan0'), modem_status()
    good = wifi == 'connected' and modem['bearer'] == 'connected' and ts == 'Running' and clock == 'synchronized'
    return dict(updated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'), uptime=uptime, temperature=temperature, clock=clock, wifi=wifi, modem=modem, route=preferred_route(), tailscale=ts, probe=recorded_probe(probe_path), events=recent_events(), summary='Core services reporting normally' if good else 'Review current status', detail='Wi-Fi and cellular bearer are connected. Remote access over cellular remains unverified.' if good else 'Some services are disconnected, unsynchronized, or unavailable. Check the details below.')


def render(data):
    esc = lambda value: html.escape(str(value), quote=True)
    modem = data['modem']
    rows = [('Wi-Fi', data['wifi']), ('Cellular bearer', modem['bearer']), ('Preferred underlying route', data['route']), ('Network registration', modem['registration']), ('Access technology', modem['technology']), ('Signal', modem['signal']), ('Tailscale', data['tailscale']), ('Clock synchronization', data['clock']), ('Latest cellular probe', data['probe'])]
    rows_html = ''.join(f'<div class="row"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in rows)
    events = ''.join(f'<li><time>{esc(t)}</time><span>{esc(m)}</span></li>' for t, m in data['events'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Buoy Link status</title><style>
:root{{color-scheme:light;--ink:#102e36;--muted:#48626a;--line:#c6d8d7;--paper:#f2f7f5}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}main{{max-width:1050px;margin:auto;padding:38px 28px 60px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px}}h1{{font-size:clamp(1.8rem,4vw,2.6rem);letter-spacing:-.025em;margin:0}}h2{{font-size:1.18rem;margin:0 0 14px}}p{{margin:0}}.muted,time{{color:var(--muted)}}button{{background:var(--ink);color:white;border:0;border-radius:8px;padding:10px 18px;font:inherit;cursor:pointer}}button:focus-visible{{outline:3px solid #168f82;outline-offset:3px}}.summary{{padding:28px 0;border-bottom:1px solid var(--line)}}.summary h2{{font-size:1.5rem;margin:0 0 5px}}.metrics{{display:flex;gap:42px;margin-top:22px}}.metrics strong{{display:block;font-size:1.3rem;font-variant-numeric:tabular-nums}}.layout{{display:grid;grid-template-columns:1.3fr 1fr;gap:52px;margin-top:32px}}dl{{margin:0}}.row{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:11px 0}}dt{{color:var(--muted)}}dd{{margin:0;text-align:right;overflow-wrap:anywhere;font-weight:600}}ul{{list-style:none;margin:0;padding:0}}li{{padding:11px 0;border-bottom:1px solid var(--line)}}time{{display:block;font-size:.8rem;font-variant-numeric:tabular-nums}}.notice{{margin-top:26px;font-size:.9rem;color:var(--muted)}}@media(max-width:680px){{main{{padding:24px 20px 44px}}header{{align-items:flex-start}}.layout{{grid-template-columns:1fr;gap:32px}}.metrics{{gap:26px;flex-wrap:wrap}}.row{{align-items:baseline}}}}
</style></head><body><main><header><div><h1>Buoy Link</h1><p class="muted">System status · {esc(data['updated'])}</p></div><form method="get" action="/"><button type="submit">Refresh</button></form></header><section class="summary"><h2>{esc(data['summary'])}</h2><p class="muted">{esc(data['detail'])}</p><div class="metrics"><div><span class="muted">Uptime</span><strong>{esc(data['uptime'])}</strong></div><div><span class="muted">Temperature</span><strong>{esc(data['temperature'])}</strong></div></div></section><div class="layout"><section><h2>Connections &amp; system</h2><dl>{rows_html}</dl><p class="notice">Cellular-only Tailscale access has not been proven. This page does not start a probe.</p></section><section><h2>Recent events</h2><p class="muted">Recent service warnings and errors</p><ul>{events}</ul><p class="notice">Event details are withheld to protect identifiers and credentials.</p></section></div></main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description='Read-only local buoy dashboard')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--probe-result', help='optional JSON probe result file with recorded_at timestamp')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            body = render(collect_status(args.probe_result)).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, format, *args):
            pass
    print(f'Buoy Link dashboard: http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
