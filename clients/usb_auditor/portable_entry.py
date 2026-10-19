"""Preflight before importing collectors; shared entry for the two ONEDIR EXEs."""
import argparse
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time
import uuid


def _windows():
    if sys.platform != 'win32':
        raise OSError('Windows x64 is required')
    return ctypes.WinDLL('advapi32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)


def current_sid():
    adv, kernel = _windows()
    kernel.GetCurrentProcess.restype = w.HANDLE
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    adv.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [w.LPVOID, ctypes.POINTER(w.LPWSTR)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.LocalFree.argtypes = [w.LPVOID]
    token, needed = w.HANDLE(), w.DWORD()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        if not adv.GetTokenInformation(token, 1, buffer, needed, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buffer, ctypes.POINTER(w.LPVOID))[0]
        text = w.LPWSTR()
        if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text, w.LPVOID))
    finally:
        kernel.CloseHandle(token)


def protect_new_directory(path):
    adv, kernel = _windows()
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.DWORD)]
    adv.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, w.LPVOID]
    kernel.LocalFree.argtypes = [w.LPVOID]
    descriptor = w.LPVOID()
    sid = current_sid()
    sddl = f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)'
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not adv.SetFileSecurityW(str(path), 0x80000005, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


def volume_info(path):
    _, kernel = _windows()
    kernel.GetVolumePathNameW.argtypes = [w.LPCWSTR, w.LPWSTR, w.DWORD]
    kernel.GetVolumeInformationW.argtypes = [w.LPCWSTR, w.LPWSTR, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD), w.LPWSTR, w.DWORD]
    kernel.GetDriveTypeW.argtypes = [w.LPCWSTR]
    root, flags = ctypes.create_unicode_buffer(1024), w.DWORD()
    if not kernel.GetVolumePathNameW(str(path), root, len(root)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.GetVolumeInformationW(root.value, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel.GetDriveTypeW(root.value), bool(flags.value & 8)


def verify_private_acl(path):
    adv, kernel = _windows()
    adv.GetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)]
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [w.LPVOID, w.DWORD, w.DWORD, ctypes.POINTER(w.LPWSTR), ctypes.POINTER(w.DWORD)]
    kernel.LocalFree.argtypes = [w.LPVOID]
    size = w.DWORD()
    adv.GetFileSecurityW(str(path), 5, None, 0, ctypes.byref(size))
    descriptor = ctypes.create_string_buffer(size.value)
    if not adv.GetFileSecurityW(str(path), 5, descriptor, size, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    text = w.LPWSTR()
    if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 5, ctypes.byref(text), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        sddl = text.value
        sid = current_sid()
        if not sddl.startswith('O:' + sid) or 'D:P' not in sddl:
            raise PermissionError('Existing Evidence is not a protected directory owned by this account; use a different approved --output-dir')
        for ace in re.findall(r'\(([^()]*)\)', sddl):
            parts = ace.split(';')
            if parts[0] in {'A', 'OA'} and parts[-1] not in {sid, 'SY', 'S-1-5-18'}:
                raise PermissionError('Existing Evidence permits other accounts; no collection started')
    finally:
        kernel.LocalFree(ctypes.cast(text, w.LPVOID))


def reject_links(path):
    for node in [path, *path.parents]:
        if node.exists() and (node.is_symlink() or node.is_junction()):
            raise OSError('Links/reparse destinations are not permitted')


def verify_package(root):
    """Hash consistency only; an unsigned manifest is not publisher authentication."""
    reject_links(root)
    records = {}
    reading = False
    for line in (root / 'MANIFEST.txt').read_text('utf-8').splitlines():
        if line == '--- files ---':
            reading = True
            continue
        if not reading or not line or line.startswith('#'):
            continue
        rel, size, digest = [x.strip() for x in line.split('|')]
        if rel in records or ':' in rel or '\\' in rel or rel.startswith('/') or '..' in Path(rel).parts:
            raise ValueError('Unsafe package manifest')
        records[rel] = digest
        path = root / rel
        reject_links(path)
        if path.stat().st_size != int(size) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Package integrity failure: ' + rel)
    required = {'EIMS-Auditor-Standard.exe', 'EIMS-Auditor-Admin.exe', 'VERSION.txt', 'README.txt'}
    if not required <= records.keys() or not any(p.startswith('_internal/') for p in records):
        raise ValueError('Incomplete portable package')
    for path in root.rglob('*'):
        rel = path.relative_to(root).as_posix()
        if rel == 'Evidence' or rel.startswith('Evidence/'):
            continue
        reject_links(path)
        if path.is_file() and rel not in records and rel not in {'MANIFEST.txt', 'audit-policy.json'}:
            raise ValueError('Unexpected package file: ' + rel)


def prepare_output(root, requested=None):
    path = Path(requested) if requested else root / 'Evidence'
    if not path.is_absolute() or str(path).startswith(('\\\\', '//')):
        raise ValueError('Evidence must be an absolute approved local/removable path, not a network share')
    path = path.absolute()
    reject_links(path)
    if not path.parent.is_dir() or path == path.parent or path == root or root / '_internal' in [path, *path.parents]:
        raise ValueError('Invalid Evidence destination; its parent must already exist')
    drive_type, acl_supported = volume_info(path.parent)
    if drive_type == 4:
        raise ValueError('Copy the application from the approved share to a local folder first')
    if drive_type == 2 or not acl_supported:
        # Explicit preconfigured company approval; this is NOT encryption detection.
        policy = json.loads((root / 'audit-policy.json').read_text('utf-8')) if (root / 'audit-policy.json').is_file() else {}
        if policy.get('encrypted_removable_media_approved') is not True or not policy.get('approval_reference'):
            raise PermissionError('Removable/non-ACL evidence requires company-approved encryption and an approval reference in audit-policy.json. No collection started.')
    if shutil.disk_usage(path.parent).free < 64 * 1024 * 1024:
        raise OSError('At least 64 MiB free space is required before collection')
    existed = path.exists()
    path.mkdir(exist_ok=True)
    if not path.is_dir():
        raise OSError('Evidence destination is not a directory')
    if acl_supported and not existed:
        protect_new_directory(path)
    if acl_supported:
        verify_private_acl(path)
    for name in ('reports', 'logs'):
        reject_links(path / name)
        (path / name).mkdir(exist_ok=True)
        probe = path / name / ('.write-check-' + uuid.uuid4().hex)
        try:
            with probe.open('xb') as handle:
                handle.write(b'EIMS output preflight')
                handle.flush()
                os.fsync(handle.fileno())
            if probe.read_bytes() != b'EIMS output preflight':
                raise OSError('Evidence write verification failed')
        finally:
            if probe.exists():
                probe.unlink()
    return path


def launch(mode):
    result, no_wait = 2, False
    try:
        sys.dont_write_bytecode = True
        parser = argparse.ArgumentParser(description='Authorized read-only portable Windows audit')
        parser.add_argument('--output-dir', help='Explicit approved absolute local/removable Evidence directory')
        parser.add_argument('--headless', action='store_true', help='Explicit CLI diagnostics; default opens the desktop GUI')
        parser.add_argument('--no-wait', action='store_true', help='Close immediately after printing results')
        args = parser.parse_args()
        no_wait = args.no_wait
        root = Path(sys.executable).absolute().parent if getattr(sys, 'frozen', False) else Path(__file__).absolute().parent
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        if mode == 'admin' and not admin:
            raise PermissionError('Administrator privileges were not granted; no collection started')
        if getattr(sys, 'frozen', False):
            verify_package(root)
        evidence = prepare_output(root, args.output_dir)
        os.environ.update(EIMS_REPORTS_DIR=str(evidence / 'reports'), EIMS_LOGS_DIR=str(evidence / 'logs'),
                          EIMS_AUTO_SYNC='false', EIMS_AUDITOR_MODE=mode)
        if not args.headless:
            from auditor_gui import run
            return run(evidence, mode)
        import socket
        print('EIMS Portable Windows Auditor')
        print('Target:', socket.gethostname())
        print('Privilege:', 'Administrator' if admin else 'Standard user')
        print('Mode:', 'USB' if volume_info(root)[0] == 2 else 'Local Folder')
        print('Evidence:', evidence)
        print('Network upload: Disabled')
        print('Collectors may require permitted Windows PowerShell; blocked queries remain unavailable.')
        import main as engine
        original = sys.argv
        try:
            sys.argv = [original[0], '--authorized', '--export']
            result = engine.main()
        finally:
            sys.argv = original
    except Exception as exc:
        if not getattr(sys.stdout, 'isatty', lambda: False)():
            from tkinter import messagebox
            messagebox.showerror('EIMS Auditor — no collection started', str(exc))
        print('EIMS AUDIT ERROR:', str(exc))
        print('No successful audit is claimed. Evidence was not redirected elsewhere.')
    finally:
        if not no_wait and getattr(sys.stdout, 'isatty', lambda: False)():
            print('This result window closes in 15 seconds.')
            time.sleep(15)
    return result
