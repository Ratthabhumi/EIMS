"""Bounded read-only network evidence. No rule changes or threat verdicts."""
import json
import subprocess
from scanner.processes import run_readonly

QUERIES = {
    'tcp_listeners': ('Get-NetTCPConnection -State Listen',
                      'LocalAddress,LocalPort,OwningProcess', 500),
    'udp_endpoints': ('Get-NetUDPEndpoint', 'LocalAddress,LocalPort,OwningProcess', 500),
    'inbound_rules': ('Get-NetFirewallRule -PolicyStore ActiveStore -Enabled True -Direction Inbound',
        'Name,DisplayName,Direction,Action,Profile,@{n="Port";e={$_ | Get-NetFirewallPortFilter | '
        'Select-Object Protocol,LocalPort,RemotePort}},@{n="Address";e={$_ | Get-NetFirewallAddressFilter | '
        'Select-Object LocalAddress,RemoteAddress}},@{n="Application";e={$_ | Get-NetFirewallApplicationFilter | Select-Object Program,Package}}', 200),
}


def collect_firewall_evidence():
    result = {'status': 'ok', 'interpretation': 'Observed endpoints/rules only; not proof of exposure or malicious activity.'}
    for name, (query, fields, limit) in QUERIES.items():
        command = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                   "$ErrorActionPreference='Stop'; "
                   f'ConvertTo-Json -InputObject @({query} | Select-Object -First {limit + 1} | Select-Object {fields}) '
                   '-Compress -Depth 5')
        try:
            run = run_readonly(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                 capture_output=True, text=True, encoding='utf-8', timeout=30)
            if run.returncode != 0 or not run.stdout.strip():
                raise ValueError('unavailable')
            rows = json.loads(run.stdout)
            if isinstance(rows, dict):
                rows = [rows]
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError('invalid response')
            result[name] = {'status': 'ok', 'limit': limit, 'truncated': len(rows) > limit,
                            'records': rows[:limit]}
        except (OSError, ValueError, subprocess.SubprocessError):
            result['status'] = 'partial'
            result[name] = {'status': 'unavailable', 'records': [],
                            'reason': 'Permission, platform support or query failure; engineer review required.'}
    return result
