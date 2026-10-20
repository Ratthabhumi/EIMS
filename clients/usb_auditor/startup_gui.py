"""Visible startup before slow USB verification; explicit approved output choice."""
import queue
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def select_output(package, requested, choose, explain):
    """No automatic local/AppData fallback. Every alternative is operator-selected."""
    from portable_entry import prepare_output
    while True:
        try:
            return prepare_output(package, requested)
        except (OSError, ValueError) as exc:
            # Show the reason in the existing startup window. The folder picker
            # already provides an explicit choice and Cancel; no extra Yes/No.
            explain(str(exc))
            parent = choose()
            if not parent:
                return None
            # The selected parent itself may have broad inherited permissions.
            # Preflight creates a dedicated protected Evidence child instead.
            requested = str(Path(parent) / 'EIMS_Evidence')


def prepare_gui(package, requested, mode):
    from portable_entry import verify_package, volume_info
    window = tk.Tk()
    window.title('EIMS Auditor — Starting ' + mode.title())
    window.geometry('590x250')
    window.resizable(False, False)
    body = ttk.Frame(window, padding=20)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text='Starting EIMS Auditor', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
    status = tk.StringVar(value='Opening package — no scan has started.')
    ttk.Label(body, textvariable=status, wraplength=540).pack(anchor='w', pady=12)
    bar = ttk.Progressbar(body, mode='indeterminate', length=540)
    bar.pack(fill='x');bar.start(70)
    ttk.Label(body, text='Checking files on a USB can take longer.\nKeep this window open; no collectors run during verification.',
              wraplength=540).pack(anchor='w', pady=12)
    events = queue.Queue()
    result = {}
    cancelled = threading.Event()
    def cancel():
        cancelled.set()
        window.quit()
    window.protocol('WM_DELETE_WINDOW', cancel)
    def verification():
        try:
            if volume_info(package)[0] == 4:
                raise ValueError('Copy the application from the network share to an approved local folder first.')
            if getattr(sys, 'frozen', False):
                def progress(done,total):
                    if cancelled.is_set():raise InterruptedError('Startup cancelled')
                    events.put(('progress',(done,total)))
                verify_package(package, progress=progress)
            events.put(('verified',None))
        except Exception as exc:
            events.put(('error',str(exc)))
    def poll():
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='progress':
                    done,total=value
                    bar.stop();bar.configure(mode='determinate',maximum=max(total,1),value=done)
                    status.set(f'Checking package files: {done:,} / {total:,}')
                elif kind=='verified':
                    result['verified']=True;window.quit();return
                elif kind=='error':
                    result['error']=value;window.quit();return
        except queue.Empty:pass
        if not cancelled.is_set():window.after(100,poll)
    window.after(100,poll)
    window.update()
    threading.Thread(target=verification,daemon=True).start()
    try:
        window.mainloop()
        if cancelled.is_set():return None
        if result.get('error'):
            messagebox.showerror('EIMS startup failed — no scan started',result['error'],parent=window)
            return None
        if not result.get('verified'):return None
        status.set('Package verified. Checking approved report storage…');window.update_idletasks()
        def explain(error):
            status.set(error+'\nChoose an approved parent folder, or Cancel. '
                       'Reports use its protected EIMS_Evidence subfolder. No scan has started.')
            window.update_idletasks()
        return select_output(package,requested,
            lambda:filedialog.askdirectory(title='Choose an approved LOCAL parent for EIMS_Evidence',mustexist=True,parent=window),explain)
    finally:
        cancelled.set();window.destroy()
