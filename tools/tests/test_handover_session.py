import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('hs',Path(__file__).parents[1]/'handover/handover_session.py')
hs=importlib.util.module_from_spec(spec);spec.loader.exec_module(hs)


@pytest.fixture
def context():
    return dict(server='synthetic-server',sid='S-1-5-21-synthetic',logon=7,key='ab'*32)


def test_grant_is_one_use(context):
    b=hs.Broker(context);p=hs.proof(context,100)
    b.consume(p,hs.ORIGIN,100)
    with pytest.raises(PermissionError):b.consume(p,hs.ORIGIN,100)


@pytest.mark.parametrize('case',['expired','future','bad_origin','missing','tamper','sid','session','server','restart'])
def test_unauthorized_or_wrong_session_rejected(context,case):
    signed=context.copy();now=100;origin=hs.ORIGIN
    if case in {'sid','session','server'}:signed[{'sid':'sid','session':'logon','server':'server'}[case]]='other'
    p=hs.proof(signed,100)
    if case=='expired':now=160
    if case=='future':now=99
    if case=='bad_origin':origin='http://evil.invalid'
    if case=='missing':p=None
    if case=='tamper':p=p[:-1]+('a' if p[-1]!='a' else 'b')
    if case=='restart':context={**context,'key':'cd'*32}
    with pytest.raises(PermissionError):hs.Broker(context).consume(p,origin,now)


def test_proof_contains_no_signing_key(context):
    assert context['key'] not in hs.proof(context)


def test_old_cache_cannot_checkpoint_into_new_package(tmp_path):
    spec=importlib.util.spec_from_file_location('usb_backup_test',Path(__file__).parents[1]/'handover/usb_backup.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    import json
    install=tmp_path/'install';payload=tmp_path/'package'
    install.mkdir();(payload/'Tools').mkdir(parents=True)
    (install/'installation.json').write_text(json.dumps({'id':'old'}))
    (payload/'Tools/package.json').write_text(json.dumps({'id':'new'}))
    with pytest.raises(ValueError,match='identity changed'):b.checkpoint(install,payload)
    assert not (tmp_path/'EIMS_Data').exists()


def test_synthetic_reports_are_importable_and_fictional():
    import sys,ipaddress
    sys.path.insert(0,str(Path(__file__).parents[1]/'handover'))
    sys.path.insert(0,str(Path(__file__).parents[2]/'clients/usb_auditor'))
    from synthetic_demo import reports
    from session_model import validate_context,FIELDS
    rows=reports();assert len(rows)==3
    assert len({r['system']['computer_name'] for r in rows})==3
    for r in rows:
        assert r['classification']=='SYNTHETIC_DEMO'
        assert ipaddress.ip_address(r['system']['ip_address']) in ipaddress.ip_network('192.0.2.0/24')
        assert len(r['event_logs']['events'])>10
        validate_context({k:r[k] for k in FIELDS if k in r})
