"""Synthetic acceptance for scope execution, immutable review and GUI controls."""
import copy
import json
import logging
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from session_model import MODULES, validate_context


def test_disabled_modules_never_execute_or_affect_applicable_score(monkeypatch,tmp_path):
    import main
    from exporters import json_exporter
    monkeypatch.setattr(json_exporter,'REPORTS_DIR',tmp_path)
    def forbidden():raise AssertionError('Disabled collector executed')
    for name in ('get_system_info','get_security_info','get_services_info','get_registry_info','get_setup_verify_info','collect_event_logs','collect_firewall_evidence'):
        monkeypatch.setattr(main,name,forbidden)
    result={};stages=[]
    code=main.run_scan(logging.getLogger('test'),result,dict.fromkeys(MODULES,False),
                       {'customer':{'company':'Synthetic'}},lambda n,label:stages.append(n))
    assert code==3 and stages==list(range(1,10))
    report=json.loads(result['report_path'].read_text())
    assert report['system']['inventory_status']=='SKIPPED_BY_OPERATOR'
    assert report['security']['defender']['status']=='SKIPPED_BY_OPERATOR'
    assert report['compliance']['total_checks']==0
    assert report['event_logs']['events']==[] and report['event_logs']['status']=='SKIPPED_BY_OPERATOR'
    assert not any(report['selected_modules'].values())


def test_secret_fields_and_evidence_are_not_business_context():
    with pytest.raises(ValueError):validate_context({'customer':{'password':'x'}})
    with pytest.raises(ValueError):validate_context({'system':{'computer_name':'forged'}})
    with pytest.raises(ValueError):validate_context({'audit_context':{'notes':'x'*2001}})


def test_actual_tk_fields_annotations_and_literal_excel(monkeypatch,tmp_path):
    import tkinter as tk
    from auditor_gui import AuditorGUI
    from exporters import json_exporter,excel_exporter
    root=tk.Tk()
    try:
        app=AuditorGUI(root,tmp_path,'standard')
        root.update()
        assert root.winfo_viewable() and len(app.fields)==13
        assert not any('password' in key.lower() for _,key in app.fields)
        app.fields['customer','company'].set('=SYNTHETIC_FORMULA()')
        app.fields['customer','contact_email'].set('it@example.invalid')
        app.fields['asset_context','asset_tag'].set('PC-001')
        (tmp_path/'reports').mkdir();(tmp_path/'logs').mkdir()
        monkeypatch.setattr(json_exporter,'REPORTS_DIR',tmp_path/'reports')
        monkeypatch.setattr(excel_exporter,'REPORTS_DIR',tmp_path/'reports')
        raw={'system':{'computer_name':'SYNTHETIC','collection_privileges':'standard_user'},'security':{'defender':{'status':'UNKNOWN','detail':'blocked'}},'services':{},'registry':{},'compliance':{'score':0,'verdict':'Partial'}}
        original=copy.deepcopy(raw)
        from session_model import findings
        app.report=raw;app.context={'selected_modules':dict.fromkeys(MODULES,True)}
        app.rows={row[0]:row for row in findings(raw)}
        app.tree.insert('','end',iid='security.defender',values=('UNKNOWN','Defender'))
        app.tree.selection_set('security.defender');app.select_finding()
        assert str(app.detail['state'])=='disabled'
        app.manual['review_status'].set('Investigating');app.manual['note'].set('Manual verification required')
        app.apply_annotation();app.export()
        ticks=0;deadline=time.monotonic()+10
        while app.busy and time.monotonic()<deadline:
            root.update();ticks+=1;time.sleep(.01)
        assert not app.busy and ticks>1
        assert raw==original
        output=json.loads(next((tmp_path/'reports').glob('*.json')).read_text())
        assert output['customer']['contact_email']=='it@example.invalid'
        assert output['manual_annotations'][0]['review_status']=='Investigating'
        assert output['manual_change_log'][0]['identity_source']=='local_os_user_not_EIMS_authentication'
        import openpyxl
        book=openpyxl.load_workbook(next((tmp_path/'reports').glob('*.xlsx')))
        assert book['Business Context']['D2'].value=='=SYNTHETIC_FORMULA()'
        assert book['Business Context']['D2'].data_type=='s'
        assert book['Manual Review']['C2'].value=='Investigating'
    finally:root.destroy()
