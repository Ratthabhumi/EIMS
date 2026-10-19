"""Bounded non-secret operator context, always separate from scanner evidence."""
import copy
import getpass
import hashlib
import json
import platform
import socket
import uuid
from datetime import datetime, timezone

MODULES = {'inventory': 'Hardware & Windows Inventory', 'windows_events': 'Windows Event Logs',
           'firewall': 'Windows Firewall / Open Ports', 'security': 'Defender / BitLocker / Security',
           'services_registry': 'Services & Registry Checks'}
FIELDS = {
    'customer': {'company': 'Customer / Company', 'site': 'Site / Branch', 'department': 'Department',
                 'contact_name': 'Contact Person / PC Owner', 'contact_email': 'Contact Email (optional)'},
    'asset_context': {'asset_tag': 'Asset Tag', 'assigned_user': 'Assigned User / Username',
                      'business_location': 'Business Location', 'device_role': 'Device Purpose / Role'},
    'audit_context': {'engineer': 'Engineer Name', 'ticket_id': 'Ticket / Job Reference',
                      'purpose': 'Audit Purpose', 'notes': 'Engineer Notes'},
}
REVIEW_STATUSES = ('Open', 'Investigating', 'Resolved', 'Accepted Risk', 'False Positive')


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, limit=500):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Text must contain at most {limit} characters')
    return value


def validate_context(value):
    allowed = {*FIELDS, 'selected_modules', 'manual_annotations', 'manual_change_log', 'context_version'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('Unsupported context field; original evidence is not editable')
    clean = {'context_version': 1}
    for group, fields in FIELDS.items():
        data = value.get(group, {})
        if not isinstance(data, dict) or set(data) - fields.keys():
            raise ValueError('Unsupported business field')
        clean[group] = {key: text(item, 2000 if key == 'notes' else 500) for key, item in data.items()}
    if 'selected_modules' in value:
        scope = value['selected_modules']
        if not isinstance(scope, dict) or set(scope) != set(MODULES) or any(type(v) is not bool for v in scope.values()):
            raise ValueError('Invalid audit module selection')
        clean['selected_modules'] = dict(scope)
    annotations = value.get('manual_annotations', [])
    if not isinstance(annotations, list) or len(annotations) > 1000:
        raise ValueError('At most 1000 annotations are supported')
    clean['manual_annotations'] = []
    for item in annotations:
        allowed_note = {'finding_id', 'review_status', 'note', 'remediation', 'ticket_reference', 'manual_correction'}
        if not isinstance(item, dict) or set(item) - allowed_note or not item.get('finding_id'):
            raise ValueError('Invalid finding annotation')
        if item.get('review_status', 'Open') not in REVIEW_STATUSES:
            raise ValueError('Invalid review status')
        clean['manual_annotations'].append({k: text(v, 2000) for k, v in item.items()})
    trail = value.get('manual_change_log', [])
    if not isinstance(trail, list) or len(trail) > 2000 or len(json.dumps(trail)) > 1024 * 1024:
        raise ValueError('Manual change log limit exceeded')
    # Incoming client audit history is descriptive, never an authenticated identity.
    for entry in trail:
        if not isinstance(entry, dict) or set(entry) - {'at', 'operator', 'identity_source', 'finding_id', 'before', 'after'}:
            raise ValueError('Invalid manual change history')
        for key in ('before', 'after'):
            if key in entry:
                validate_context({'manual_annotations': [entry[key]]})
        for key in ('at', 'operator', 'identity_source', 'finding_id'):
            if key in entry:
                text(entry[key], 2000)
    clean['manual_change_log'] = copy.deepcopy(trail)
    return clean


def minimum_identity():
    mac = f'{uuid.getnode():012X}'
    return {'computer_name': socket.gethostname(), 'username': getpass.getuser(),
            'windows_edition': platform.system(), 'mac_address': ':'.join(mac[i:i+2] for i in range(0,12,2)),
            'ip_address': '0.0.0.0', 'inventory_status': 'SKIPPED_BY_OPERATOR', 'scan_timestamp': now()}


def findings(report):
    rows = []
    for group in ('security', 'services', 'registry', 'setup_verify'):
        for key, item in report.get(group, {}).items():
            if isinstance(item, dict):
                rows.append((group + '.' + key, item.get('status', 'UNKNOWN'), key, item))
    for event in (report.get('event_logs') or {}).get('events', []):
        identity = hashlib.sha256(json.dumps(event, sort_keys=True, default=str).encode()).hexdigest()[:24]
        rows.append(('event.' + identity, event.get('severity', 'UNKNOWN'),
                     f"Event {event.get('event_id')} / {event.get('provider')}", event))
    network = report.get('firewall_evidence') or {}
    if network:
        rows.append(('firewall_evidence', network.get('status','UNKNOWN'), 'Firewall / endpoints', network))
    return rows
