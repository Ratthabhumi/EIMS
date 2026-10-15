"""Policy assertions read templates only and never resolve operational values."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def test_compose_credential_inputs_are_required_environment_references():
    source=(ROOT/'docker-compose.yml').read_text()
    for key in ('POSTGRES_PASSWORD','DATABASE_URL','AUTH_PASS','MINIO_ROOT_USER','MINIO_ROOT_PASSWORD'):
        values=re.findall(r'^\s*'+key+r':\s*(.+)$',source,re.M)
        assert values and all('${EIMS_' in value and ':?' in value for value in values),key
    assert 'GF_SECURITY_ADMIN_PASSWORD=${EIMS_GRAFANA_ADMIN_PASSWORD:?' in source
    assert '$$MINIO_ROOT_PASSWORD' in source

def test_environment_example_contains_no_operational_credentials():
    for line in (ROOT/'.env.example').read_text().splitlines():
        key,sep,value=line.partition('=')
        if sep and key.startswith('EIMS_') and not key.endswith('EXPIRES_MINUTES') and any(word in key for word in ('PASSWORD','SECRET','TOKEN','ACCESS_KEY','DATABASE_URL')):
            assert value=='',key
