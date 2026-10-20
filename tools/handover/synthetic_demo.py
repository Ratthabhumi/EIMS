"""Fictional handover examples. Never invokes a scanner or reads workplace data."""
import json
from pathlib import Path


def reports():
    rows=[]
    for i,(host,score,status,mode) in enumerate([
        ('PC-DEMO-001',100,'PASS','standard_user'),('PC-DEMO-002',40,'FAIL','administrator'),
        ('SRV-DEMO-001',75,'WARNING','administrator')],1):
        row=dict(classification='SYNTHETIC_DEMO',demo=True,
            metadata={'classification':'SYNTHETIC_DEMO','generator':'EIMS synthetic fixtures; not a live scan'},
            system={'computer_name':host,'ip_address':f'192.0.2.{i}',
                'mac_address':f'02:00:00:00:DE:{i:02X}','serial_number':f'SYNTHETIC-DEMO-{i:03}',
                'os_name':'Windows Server (SYNTHETIC_DEMO)' if i==3 else 'Windows 11 Pro (SYNTHETIC_DEMO)',
                'os_version':'Windows Server' if i==3 else 'Windows 11 Pro',
                'collection_privileges':mode,'username':'DEMO-ENGINEER','scan_timestamp':f'2026-10-20T0{i}:00:00Z'},
            audit_context={'engineer':'Demo Engineer','purpose':'SYNTHETIC_DEMO','notes':'Fictional findings, not a live scan'},compliance_score=score,
            customer={'company':'Example Engineering Demo','contact_name':'Demo Contact',
                'contact_email':'engineer@example.invalid'},
            security={'firewall':{'status':status},'bitlocker':{'status':'UNKNOWN' if i==1 else status},
                'defender':{'status':status}},
            engineer_notes='SYNTHETIC_DEMO: fictional findings for review, not collected from any machine.',
            event_logs={'classification':'SYNTHETIC_DEMO','events':[{'event_id':41 if i==2 else 1129,'severity':'Error' if i==2 else 'Warning',
                'occurrence_time':f'2026-10-20T0{i}:00:00Z','provider':'Microsoft-Windows-Kernel-Power' if i==2 else 'Microsoft-Windows-GroupPolicy',
                'channel':'System','record_id':100+i,'message':f'SYNTHETIC_DEMO on {host}: '+
                    ('Unexpected shutdown observed; cause not confirmed.' if i==2 else 'Network/domain controller unavailable; check connectivity.'),
                'computer':host},{'event_id':6005,'severity':'Information','channel':'System','provider':'EventLog',
                    'record_id':200+i,'occurrence_time':f'2026-10-20T0{i}:01:00Z',
                    'message':f'SYNTHETIC_DEMO: fictional informational event on {host}'}]})
        rows.append(row)
        row['compliance']={'verdict':'Compliant' if score>=70 else 'Non-Compliant'}
        # More than the automatic analysis cap leaves genuine unanalysed examples.
        for n in range(9):
            row['event_logs']['events'].append({'event_id':6005,'severity':'Information','channel':'System',
                'provider':'EventLog','record_id':300+i*20+n,'occurrence_time':f'2026-10-20T0{i}:{n+2:02}:00Z',
                'message':f'SYNTHETIC_DEMO: fictional startup record {n+1} on {host}'})
    return rows


def write(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for row in reports():
        (folder/(row['system']['computer_name']+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')


if __name__=='__main__':
    import sys
    write(sys.argv[1])
