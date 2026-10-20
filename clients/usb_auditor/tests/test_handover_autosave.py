import json
import queue
from pathlib import Path

from exporters import json_exporter, excel_exporter
from review_store import save_review


def test_collect_saves_json_summary_log_once_without_export(tmp_path, monkeypatch):
    import main
    from auditor_gui import AuditorGUI
    reports=tmp_path/'reports';reports.mkdir();(tmp_path/'logs').mkdir()
    monkeypatch.setattr(json_exporter,'REPORTS_DIR',reports)
    monkeypatch.setattr(excel_exporter,'REPORTS_DIR',reports)
    calls=[]
    def scan(logger,outcome,*args):
        calls.append(True)
        logger.warning('SYNTHETIC test log')
        outcome['report_path']=json_exporter.save_report(
            {'computer_name':'SYNTHETIC','collection_privileges':'standard_user'}, {},{},{},
            {'score':0,'verdict':'Partial'})
        return 3
    monkeypatch.setattr(main,'run_scan',scan)
    app=AuditorGUI.__new__(AuditorGUI);app.evidence=tmp_path;app.events=queue.Queue()
    app.collect({}, {})
    kind,result=app.events.get_nowait()
    assert kind=='complete' and not result[-1] and len(calls)==1
    raw=result[2];before=raw.read_bytes()
    assert len(list(reports.glob('*.json')))==1
    assert len(list((tmp_path/'logs').glob('*.log')))==1
    assert json.loads(before)['metadata']['scan_id']
    context={'manual_annotations':[{'finding_id':'security.defender','review_status':'Investigating','note':'Check later'}]}
    for _ in range(2):
        save_review(raw,context);excel_exporter.export_summary([raw])
    assert raw.read_bytes()==before and len(list(reports.glob('*.json')))==1
    assert len(list((tmp_path/'reviews').glob('*.review')))==1
    import openpyxl
    book=openpyxl.load_workbook(reports/'Summary.xlsx')
    try:assert book['Compliance Summary'].max_row==2
    finally:book.close()


def test_summary_deduplicates_scan_id_without_deleting_files(tmp_path,monkeypatch):
    monkeypatch.setattr(excel_exporter,'REPORTS_DIR',tmp_path)
    for name,mode in [('one','standard_user'),('copy','standard_user'),('admin','administrator')]:
        data={'metadata':{'scan_id':'same' if mode=='standard_user' else 'different'},
              'system':{'computer_name':'SYNTHETIC','collection_privileges':mode}}
        (tmp_path/(name+'.json')).write_text(json.dumps(data))
    assert len(excel_exporter._load_reports())==2
    assert len(list(tmp_path.glob('*.json')))==3
