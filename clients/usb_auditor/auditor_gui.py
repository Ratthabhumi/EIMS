"""One offline Tk GUI shared by both privilege manifests; collectors stay in main."""
import copy
import getpass
import json
import logging
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from uuid import uuid4

from session_model import FIELDS, MODULES, REVIEW_STATUSES, findings, now, validate_context


class AuditorGUI:
    def __init__(self, root, evidence, mode):
        self.root, self.evidence, self.mode = root, Path(evidence), mode
        self.events = queue.Queue()
        self.report = None
        self.report_path = None
        self.review_dirty = False
        self.context = {}
        self.rows, self.annotations, self.trail = {}, {}, []
        self.busy = False
        root.title('EIMS Auditor — ' + mode.title())
        root.geometry('1100x680')
        root.minsize(900, 620)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TLabel', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=7)
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='EIMS  |  Windows Evidence Auditor', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        import main as engine
        privilege = 'Administrator' if engine.is_admin() else 'Standard user'
        ttk.Label(outer, text=f'{mode.title()} EXE  •  Actual privilege: {privilege}  •  Offline / no automatic upload').pack(anchor='w', pady=5)
        ttk.Label(outer, text='Authorized devices only. Some checks require permitted Windows PowerShell. Blocked checks remain unavailable.').pack(anchor='w')
        footer = ttk.Frame(outer)
        footer.pack(side='bottom', fill='x')
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True, pady=10)
        info, config, review = [ttk.Frame(self.tabs, padding=12) for _ in range(3)]
        for frame, title in zip((info, config, review), ('1  Customer & Asset', '2  Audit Configuration', '3  Review & Export')):
            self.tabs.add(frame, text=title)
        # Keep every review control reachable on short screens, including paths.
        review_page = review
        self.review_canvas = tk.Canvas(review_page, highlightthickness=0)
        scrollbar = ttk.Scrollbar(review_page, orient='vertical', command=self.review_canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.review_canvas.pack(side='left', fill='both', expand=True)
        self.review_canvas.configure(yscrollcommand=scrollbar.set)
        review = ttk.Frame(self.review_canvas)
        pane = self.review_canvas.create_window((0,0), window=review, anchor='nw')
        review.bind('<Configure>', lambda event:self.review_canvas.configure(scrollregion=self.review_canvas.bbox('all')))
        self.review_canvas.bind('<Configure>', lambda event:self.review_canvas.itemconfigure(pane,width=event.width))
        self.fields = {}
        pos = 0
        for group, fields in FIELDS.items():
            for key, label in fields.items():
                column, row = (pos % 2) * 2, pos // 2
                ttk.Label(info, text=label).grid(row=row, column=column, sticky='w', padx=5, pady=9)
                var = tk.StringVar()
                entry = ttk.Entry(info, textvariable=var, width=30)
                entry.grid(row=row, column=column+1, sticky='ew', padx=5)
                self.fields[group, key] = var
                pos += 1
        info.columnconfigure(1, weight=1)
        info.columnconfigure(3, weight=1)
        ttk.Label(info, text='All fields optional. Do not enter passwords, tokens or recovery secrets.', wraplength=900).grid(row=8, column=0, columnspan=4, sticky='w', pady=12)
        self.modules = {}
        for name, label in MODULES.items():
            var = tk.BooleanVar(value=True)
            self.modules[name] = var
            ttk.Checkbutton(config, text=label, variable=var).pack(anchor='w', pady=10)
        ttk.Label(config, text='Unchecked modules are not collected and do not contribute to compliance scoring.\nMinimum machine identity is retained for provenance.\nEvidence location: ' + str(evidence), wraplength=950).pack(anchor='w', pady=15)
        self.summary = tk.StringVar(value='Start an audit to review observed evidence.')
        ttk.Label(review, textvariable=self.summary, wraplength=1030).pack(anchor='w')
        self.tree = ttk.Treeview(review, columns=('status', 'finding'), show='headings', height=4)
        self.tree.heading('status', text='Evidence status')
        self.tree.heading('finding', text='Finding — select for original evidence')
        self.tree.column('status', width=150, stretch=False)
        self.tree.pack(fill='x', pady=6)
        self.tree.bind('<<TreeviewSelect>>', self.select_finding)
        self.detail = tk.Text(review, height=3, wrap='word', state='disabled', font=('Consolas', 9))
        self.detail.pack(fill='both', expand=True)
        form = ttk.Frame(review)
        form.pack(fill='x', pady=5)
        self.manual = {}
        for index, (key, label) in enumerate((('review_status','Review Status'),('ticket_reference','Ticket Reference'),
                                             ('note','Engineer Note'),('remediation','Remediation Recommendation'),
                                             ('manual_correction','Proposed correction + explanation (does not edit evidence)'))):
            ttk.Label(form, text=label, wraplength=270).grid(row=index, column=0, sticky='w')
            var = tk.StringVar(value='Open' if key == 'review_status' else '')
            self.manual[key] = var
            widget = ttk.Combobox(form, textvariable=var, values=REVIEW_STATUSES, state='readonly') if key=='review_status' else ttk.Entry(form,textvariable=var)
            widget.grid(row=index,column=1,sticky='ew',pady=2)
        form.columnconfigure(1,weight=1)
        ttk.Button(form, text='Apply annotation', command=self.apply_annotation).grid(row=0,column=2,padx=8)
        self.progress = ttk.Progressbar(footer, maximum=9)
        self.progress.pack(fill='x')
        self.status = tk.StringVar(value='Ready — no scan has started')
        ttk.Label(footer,textvariable=self.status,wraplength=1050).pack(anchor='w',pady=4)
        bar=ttk.Frame(footer);bar.pack(fill='x')
        self.start_button=ttk.Button(bar,text='Start Audit',command=self.start);self.start_button.pack(side='left')
        self.export_button=ttk.Button(bar,text='Save Review',command=self.export,state='disabled');self.export_button.pack(side='left',padx=8)
        self.retry_button=ttk.Button(bar,text='Retry Excel',command=self.retry_summary,state='disabled');self.retry_button.pack(side='left',padx=8)
        ttk.Button(bar,text='Open Evidence folder',command=lambda:os.startfile(self.evidence)).pack(side='left')
        ttk.Button(bar,text='New audit (clear customer fields)',command=self.reset).pack(side='right')
        self.paths=tk.StringVar(value=str(evidence))
        ttk.Label(footer,textvariable=self.paths,wraplength=1050,font=('Segoe UI',9)).pack(anchor='w',pady=4)
        self.tabs.select(0)
        for var in self.fields.values():var.trace_add('write',self.mark_dirty)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100,self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Audit running','Please wait for collection/export to finish.');return
        self.root.destroy()

    def reset(self):
        if self.busy:return
        if self.report and not messagebox.askyesno('New audit','Clear this session? Saved evidence remains on disk.'):
            return
        for var in self.fields.values():var.set('')
        for var in self.modules.values():var.set(True)
        self.report=None;self.report_path=None;self.review_dirty=False;self.retry_button.configure(state='disabled');self.annotations={};self.trail=[];self.rows={};self.context={}
        for field,var in self.manual.items():var.set('Open' if field=='review_status' else '')
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.configure(state='disabled')
        self.tree.delete(*self.tree.get_children())
        self.start_button.configure(state='normal');self.export_button.configure(state='disabled')
        self.summary.set('Ready for a new customer; prior profiles are not loaded.')
        self.tabs.select(0)

    def start(self):
        if self.busy:return
        try:
            context=validate_context({group:{key:self.fields[group,key].get() for key in fields} for group,fields in FIELDS.items()})
        except ValueError as exc:messagebox.showerror('Input too long',str(exc));return
        self.context=context
        scope={key:var.get() for key,var in self.modules.items()}
        self.busy=True;self.start_button.configure(state='disabled')
        self.tabs.select(2)
        threading.Thread(target=self.collect,args=(scope,context),daemon=True).start()

    def collect(self,scope,context):
        try:
            import main as engine
            path=self.evidence/'logs'/('audit-'+uuid4().hex+'.log')
            engine.setup_logging(path)
            result={}
            code=engine.run_scan(logging.getLogger('auditor.gui'),result,scope,context,
                                 lambda n,label:self.events.put(('progress',(n,label))))
            if not result.get('report_path'):raise RuntimeError('Scan failed; no successful report was produced. See execution log: '+str(path))
            report=json.loads(result['report_path'].read_text(encoding='utf-8'))
            warning=''
            try:
                from exporters.excel_exporter import export_summary
                export_summary([result['report_path']])
            except Exception as exc:warning=str(exc)
            self.events.put(('complete',(report,code,result['report_path'],path,warning)))
        except Exception as exc:self.events.put(('error',str(exc)))

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='progress':self.progress['value']=value[0];self.status.set(f'{value[0]}/9 — {value[1]}')
                elif kind=='complete':
                    self.report,code,json_path,log_path,warning=value
                    self.report_path=json_path;self.review_dirty=False
                    self.busy=False
                    self.context.update({key:self.report[key] for key in ('selected_modules','context_version')})
                    self.rows={row[0]:row for row in findings(self.report)}
                    for key,status,title,_ in self.rows.values():self.tree.insert('', 'end',iid=key,values=(status,title))
                    system=self.report['system'];events=self.report.get('event_logs') or {};network=self.report.get('firewall_evidence') or {}
                    counts={level:sum(str(e.get('severity','')).lower()==level.lower() for e in events.get('events',[])) for level in ('Critical','Error','Warning')}
                    endpoints=' / '.join(f"{key}: {len((network.get(key) or {}).get('records',[]))}" for key in ('tcp_listeners','udp_endpoints','inbound_rules'))
                    compliance=self.report['compliance']
                    check_summary=' / '.join(f'{key}: {compliance.get(key,0)}' for key in ('pass_count','warning_count','fail_count','unknown_count'))
                    self.summary.set(f"{system.get('computer_name')} | {system.get('windows_edition')} {system.get('build_number','')} | CPU {system.get('cpu','N/A')} | RAM {system.get('ram_gb','N/A')} GB | Disk {system.get('disk_gb','N/A')} GB | IP {system.get('ip_address')}\nPrivilege: {system.get('collection_privileges')} | {compliance.get('verdict')} | {check_summary}\nEvents {events.get('collected',0)} {counts} | {endpoints}\nCollection limitations: {system.get('collection_limitations',[])}; inspect UNKNOWN/PARTIAL findings below.")
                    self.status.set(('Audit Completed — JSON/Log Saved; Excel needs retry: '+warning) if warning else ('Audit Completed — Saved (PARTIAL findings)' if code==3 else 'Audit Completed — Saved'))
                    self.retry_button.configure(state='normal' if warning else 'disabled')
                    self.paths.set(f'Original JSON: {json_path}\nExcel: {json_path.parent / "Summary.xlsx"}\nLog: {log_path}')
                    self.export_button.configure(state='disabled')
                elif kind=='exported':
                    self.busy=False;self.review_dirty=False;self.export_button.configure(state='disabled')
                    self.status.set('Review Saved; original JSON is unchanged.'+(' Excel needs retry: '+value if value else ''))
                    self.retry_button.configure(state='normal' if value else 'disabled')
                elif kind=='summary':
                    self.busy=False;self.retry_button.configure(state='normal' if value else 'disabled')
                    self.status.set('Excel needs retry: '+value if value else 'Summary.xlsx Saved — no new scan.')
                elif kind=='error':
                    self.busy=False;self.start_button.configure(state='normal' if not self.report else 'disabled')
                    if self.report:self.export_button.configure(state='normal')
                    self.status.set('ERROR — '+value);messagebox.showerror('EIMS Auditor',value)
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def select_finding(self,_event=None):
        keys=self.tree.selection()
        if not keys:return
        key=keys[0];row=self.rows[key]
        self.detail.configure(state='normal');self.detail.delete('1.0','end')
        self.detail.insert('1.0',json.dumps(row[3],indent=2,ensure_ascii=False));self.detail.configure(state='disabled')
        item=self.annotations.get(key,{})
        for field,var in self.manual.items():var.set(item.get(field,'Open' if field=='review_status' else ''))

    def apply_annotation(self):
        if self.busy or not self.tree.selection():return
        key=self.tree.selection()[0]
        item={'finding_id':key,**{field:var.get() for field,var in self.manual.items()}}
        try:validate_context({'manual_annotations':[item]})
        except ValueError as exc:messagebox.showerror('Invalid annotation',str(exc));return
        before=self.annotations.get(key,{'finding_id':key})
        if before==item:return
        self.trail.append({'at':now(),'operator':getpass.getuser(),'identity_source':'local_os_user_not_EIMS_authentication',
                           'finding_id':key,'before':copy.deepcopy(before),'after':copy.deepcopy(item)})
        self.annotations[key]=item
        self.mark_dirty()
        self.status.set('Annotation applied separately from original evidence. Save Review to keep it.')

    def mark_dirty(self,*_):
        if self.report and not self.busy:
            self.review_dirty=True;self.export_button.configure(state='normal')

    def retry_summary(self):
        if self.busy or not self.report:return
        self.busy=True;self.retry_button.configure(state='disabled')
        def worker():
            warning=''
            try:
                from exporters.excel_exporter import export_summary
                export_summary([self.report_path])
            except Exception as exc:warning=str(exc)
            self.events.put(('summary',warning))
        threading.Thread(target=worker,daemon=True).start()

    def export(self):
        if self.busy or not self.report:return
        self.apply_annotation()
        # Allow business corrections before export; snapshot validation is bounded.
        try:
            context=validate_context({**self.context,
                **{group:{key:self.fields[group,key].get() for key in fields} for group,fields in FIELDS.items()},
                'manual_annotations':list(self.annotations.values()),'manual_change_log':self.trail})
        except ValueError as exc:messagebox.showerror('Invalid context',str(exc));return
        if not self.review_dirty:return
        self.busy=True;self.export_button.configure(state='disabled')
        def worker():
            try:
                from review_store import save_review
                from exporters.excel_exporter import export_summary
                save_review(self.report_path,context)
                warning=''
                try:export_summary([self.report_path])
                except Exception as exc:warning=str(exc)
                self.events.put(('exported',warning))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()


def run(evidence,mode):
    root=tk.Tk()
    AuditorGUI(root,evidence,mode)
    root.mainloop()
    return 0
