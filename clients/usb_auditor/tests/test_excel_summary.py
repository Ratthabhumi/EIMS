import ctypes
from ctypes import wintypes
import json
import sys

import openpyxl
import pytest

from exporters import excel_exporter as exporter


def report(folder, name, computer='PC-A', mode='standard_user', timestamp='2026-10-20T07:02:00'):
    path = folder / name
    path.write_text(json.dumps({'system': {'computer_name': computer, 'collection_privileges': mode,
        'scan_timestamp': timestamp}, 'customer': {'company': '=SYNTHETIC()', 'site': 'Synthetic site'},
        'asset_context': {'asset_tag': 'SYNTHETIC-ASSET'}, 'metadata': {'generated_at': timestamp}}), encoding='utf-8')
    return path


def rows(path):
    with path.open('rb') as stream:
        book = openpyxl.load_workbook(stream)
        try:
            values = list(book['Compliance Summary'].values)
            return [dict(zip(values[0], row)) for row in values[1:]]
        finally:
            book.close()


def test_all_pcs_repeat_scans_and_modes_share_one_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'REPORTS_DIR', tmp_path)
    first = report(tmp_path, 'a.json')
    output = exporter.export_summary([first])
    assert output == tmp_path / 'Summary.xlsx'
    report(tmp_path, 'b.json', mode='administrator', timestamp='2026-10-20T07:06:00')
    report(tmp_path, 'c.json', computer='PC-B', timestamp='2026-10-20T09:30:00')
    last = report(tmp_path, 'd.json', computer='PC-C', mode='administrator', timestamp='2026-10-20T10:15:00')
    original = {p.name: p.read_bytes() for p in tmp_path.glob('*.json')}
    assert exporter.export_summary([last]) == output  # Same call used by the GUI.
    data = rows(output)
    assert [r['Computer Name'] for r in data] == ['PC-A', 'PC-A', 'PC-B', 'PC-C']
    assert [r['Audit Mode'] for r in data] == ['Standard', 'Admin', 'Standard', 'Admin']
    assert data[0]['Scan Date'] == '2026-10-20T07:02:00'
    assert data[0]['Customer / Company'] == '=SYNTHETIC()'
    assert data[0]['Asset Tag'] == 'SYNTHETIC-ASSET'
    assert len({r['Report File'] for r in data}) == 4
    exporter.export_summary()
    assert len(rows(output)) == 4
    assert list(tmp_path.glob('*.xlsx')) == [output]
    assert {p.name: p.read_bytes() for p in tmp_path.glob('*.json')} == original
    assert not list(tmp_path.glob('.Summary-*.tmp'))


def test_save_failure_preserves_previous_summary_and_json(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'REPORTS_DIR', tmp_path)
    path = report(tmp_path, 'a.json')
    output = exporter.export_summary()
    previous = output.read_bytes()
    raw = path.read_bytes()
    def failed(*args, **kwargs):
        raise OSError('synthetic disk full')
    monkeypatch.setattr(openpyxl.Workbook, 'save', failed)
    with pytest.raises(OSError):
        exporter.export_summary()
    assert output.read_bytes() == previous and path.read_bytes() == raw
    assert not list(tmp_path.glob('.Summary-*.tmp'))


def test_invalid_json_does_not_silently_reduce_existing_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'REPORTS_DIR', tmp_path)
    report(tmp_path, 'a.json')
    output = exporter.export_summary()
    previous = output.read_bytes()
    (tmp_path / 'incomplete.json').write_text('{')
    with pytest.raises(OSError):
        exporter.export_summary()
    assert output.read_bytes() == previous


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows file sharing lock')
def test_real_windows_excel_style_lock_keeps_old_workbook(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'REPORTS_DIR', tmp_path)
    report(tmp_path, 'a.json')
    output = exporter.export_summary()
    previous = output.read_bytes()
    second = report(tmp_path, 'b.json', computer='PC-B')
    raw = second.read_bytes()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(output), 0x80000000, 1, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        with pytest.raises(PermissionError):
            exporter.export_summary([second])
        assert output.read_bytes() == previous and second.read_bytes() == raw
    finally:
        kernel.CloseHandle(handle)
    assert not list(tmp_path.glob('.Summary-*.tmp'))
    assert exporter.export_summary([second]) == output
    assert len(rows(output)) == 2
