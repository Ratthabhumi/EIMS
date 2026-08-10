import customtkinter as ctk
from typing import List

from app.constants import Event
from app.models.job import ProcessingJob, JobStatus
from app.viewmodels.app_viewmodel import AppViewModel


class HistoryTab:
    """Scrollable list of completed jobs with status colour coding."""

    def __init__(self, parent: ctk.CTkFrame, viewmodel: AppViewModel) -> None:
        self._vm = viewmodel
        self._frame = parent

        self._build()
        self._bind_vm_events()
        self._refresh(self._vm.history)

    def _build(self) -> None:
        self._frame.columnconfigure(0, weight=1)
        self._frame.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self._frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            header,
            text="Job History",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Clear",
            width=80,
            fg_color="#3a3a3a",
            hover_color="#555555",
            command=self._clear,
        ).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(self._frame, corner_radius=8)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self._scroll.columnconfigure(0, weight=1)

        self._rows: List[ctk.CTkFrame] = []

    def _bind_vm_events(self) -> None:
        self._vm.subscribe(
            Event.HISTORY_UPDATED,
            lambda data: self._frame.after(0, lambda d=data: self._refresh(d)),
        )

    def _refresh(self, jobs: List[ProcessingJob]) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        for job in jobs:
            row = self._make_row(job)
            row.pack(fill="x", padx=4, pady=3)
            self._rows.append(row)

    def _make_row(self, job: ProcessingJob) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._scroll, corner_radius=6, fg_color=("#2b2b2b", "#2b2b2b"))
        row.columnconfigure(1, weight=0)
        has_error = bool(job.error_message)

        # Colour indicator strip (height=24 avoids CustomTkinter 200px default height bug)
        color = job.status.color()
        indicator = ctk.CTkFrame(row, width=5, height=24, corner_radius=0, fg_color=color)
        indicator.grid(row=0, column=0, rowspan=2 if has_error else 1, sticky="ns", padx=(0, 10))

        # Timestamp
        ts = (job.processed_at or job.created_at).strftime("%H:%M:%S")
        ctk.CTkLabel(
            row,
            text=ts,
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            width=70,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(8, 2 if has_error else 8))

        # Folder name or status description
        main_text = job.folder_name if job.folder_name else job.image_path.name
        ctk.CTkLabel(
            row,
            text=main_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(0, 12), pady=(8, 2 if has_error else 8))

        # Status badge
        status_label = ctk.CTkLabel(
            row,
            text=job.status.label(),
            font=ctk.CTkFont(size=11),
            text_color=color,
            width=100,
            anchor="e",
        )
        status_label.grid(row=0, column=3, sticky="e", padx=(0, 12), pady=(8, 2 if has_error else 8))

        # Error message if any
        if has_error:
            ctk.CTkLabel(
                row,
                text=job.error_message,
                font=ctk.CTkFont(size=11),
                text_color="#a1a1aa",
                anchor="w",
            ).grid(row=1, column=1, columnspan=3, sticky="w", padx=(0, 12), pady=(0, 8))

        row.grid_columnconfigure(2, weight=1)
        return row

    def _clear(self) -> None:
        self._vm.clear_history()
