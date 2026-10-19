from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def test_storage_failure_requires_explicit_choice_and_keeps_actual_error(monkeypatch,tmp_path):
    import portable_entry
    from startup_gui import select_output
    calls=[];messages=[]
    def prepare(package,requested):
        calls.append(requested)
        if requested is None:raise PermissionError('FAT32 requires approved storage')
        return Path(requested)
    monkeypatch.setattr(portable_entry,'prepare_output',prepare)
    actual=select_output(tmp_path,None,lambda:str(tmp_path),lambda message:messages.append(message) or True)
    assert calls==[None,str(tmp_path/'EIMS_Evidence')]
    assert actual==tmp_path/'EIMS_Evidence' and messages==['FAT32 requires approved storage']


def test_decline_does_not_redirect_or_create_output(monkeypatch,tmp_path):
    import portable_entry
    from startup_gui import select_output
    def rejected(*args):raise PermissionError('Denied')
    monkeypatch.setattr(portable_entry,'prepare_output',rejected)
    def forbidden():raise AssertionError('No path selection was authorized')
    assert select_output(tmp_path,None,forbidden,lambda message:False) is None
    assert not list(tmp_path.iterdir())


def test_startup_window_is_visible_and_responsive_before_verification_finishes(monkeypatch,tmp_path):
    import portable_entry,startup_gui
    import tkinter as tk
    windows=[];ticks=[]
    original=tk.Tk
    def create():
        root=original();windows.append(root)
        def probe():
            ticks.append(root.winfo_viewable())
            root.after(50,probe)
        root.after(30,probe)
        return root
    monkeypatch.setattr(startup_gui.tk,'Tk',create)
    monkeypatch.setattr(startup_gui.sys,'frozen',True,raising=False)
    monkeypatch.setattr(portable_entry,'volume_info',lambda path:(3,True))
    def slow_verify(root,progress):
        time.sleep(.25)
        progress(1,2);time.sleep(.25);progress(2,2)
    monkeypatch.setattr(portable_entry,'verify_package',slow_verify)
    monkeypatch.setattr(portable_entry,'prepare_output',lambda root,requested:tmp_path/'Evidence')
    assert startup_gui.prepare_gui(tmp_path,None,'standard')==tmp_path/'Evidence'
    assert any(ticks), 'Startup never became visible during the slow verification'
