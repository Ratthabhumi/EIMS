import logging
import threading
from pathlib import Path
from typing import Optional

import cv2
import customtkinter as ctk
from PIL import Image as PILImage

from app.constants import Event
from app.models.job import ProcessingJob, JobStatus
from app.models.result import OCRResult
from app.services.validator import (
    validate_serial_number,
    validate_device_id,
    build_folder_name,
    sanitize_filename_str,
)
from app.viewmodels.app_viewmodel import AppViewModel

logger = logging.getLogger(__name__)

_PREVIEW_W = 860
_PREVIEW_H = 540


class ImageZoomWindow:
    """Modal window to view the sticker photo in full resolution / zoomed scale."""

    def __init__(self, parent, image_path: Path) -> None:
        self._win = ctk.CTkToplevel(parent)
        self._win.title(f"🔍 Zoom Image — {image_path.name} (ESC to close)")
        self._win.geometry("1100x850")
        self._win.attributes("-topmost", True)
        self._win.grab_set()

        self._win.bind("<Escape>", lambda _e: self._win.destroy())

        ctk.CTkLabel(
            self._win,
            text=f"🔍  {image_path.name}  ·  Press ESC or click anywhere to close",
            font=ctk.CTkFont(size=13),
            text_color="#888888",
        ).pack(pady=(10, 4))

        self._label = ctk.CTkLabel(self._win, text="")
        self._label.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._label.bind("<Button-1>", lambda _e: self._win.destroy())

        try:
            from app.services.crop_service import read_image_safe
            img_cv = read_image_safe(image_path)
            if img_cv is None:
                img_cv = cv2.imread(str(image_path))

            if img_cv is not None:
                img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                self._pil_img = PILImage.fromarray(img_rgb)
            else:
                self._pil_img = None
        except Exception:
            self._pil_img = None

        self._win.bind("<Configure>", self._on_resize)

    def _on_resize(self, event) -> None:
        if not self._pil_img or event.widget != self._win:
            return
        w = max(100, event.width - 32)
        h = max(100, event.height - 60)
        copy_img = self._pil_img.copy()
        copy_img.thumbnail((w, h), PILImage.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=copy_img, dark_image=copy_img, size=copy_img.size)
        self._label.configure(image=ctk_img, text="")


class DashboardTab:
    """
    Main working area.
    Displays queue stats, USB status, per-job stats, and
    automatically opens the preview dialog when OCR completes.
    """

    def __init__(self, parent: ctk.CTkFrame, viewmodel: AppViewModel) -> None:
        self._vm = viewmodel
        self._frame = parent
        self._preview_dialog: Optional["PreviewDialog"] = None

        self._build()
        self._bind_vm_events()
        self._refresh_usb(viewmodel.usb_path)
        self._refresh_stats(viewmodel.stats)
        self._refresh_queue(viewmodel.pending_count)

    # ------------------------------------------------------------------ #
    # Layout                                                              #
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        self._frame.columnconfigure(0, weight=0, minsize=260)
        self._frame.columnconfigure(1, weight=1)
        self._frame.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        left = ctk.CTkFrame(self._frame, corner_radius=10, fg_color=("#1e1e2e", "#1e1e2e"))
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.columnconfigure(0, weight=1)

        # USB Status card
        ctk.CTkLabel(
            left,
            text="USB Drive",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#888888",
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 2))

        self._usb_icon = ctk.CTkLabel(
            left,
            text="💾  Detecting...",
            font=ctk.CTkFont(size=14),
            anchor="w",
        )
        self._usb_icon.pack(fill="x", padx=16, pady=(0, 4))

        self._usb_label = ctk.CTkLabel(
            left,
            text="—",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            anchor="w",
        )
        self._usb_label.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkFrame(left, height=1, fg_color="#333333").pack(fill="x", padx=16)

        # Queue stats
        ctk.CTkLabel(
            left,
            text="Queue",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#888888",
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        self._pending_lbl = self._stat_row(left, "Pending", "0", "#888888")
        self._processing_lbl = self._stat_row(left, "Processing", "—", "#3b82f6")

        ctk.CTkFrame(left, height=1, fg_color="#333333").pack(fill="x", padx=16, pady=(8, 0))

        # Today's stats
        ctk.CTkLabel(
            left,
            text="Today",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#888888",
            anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        self._success_lbl = self._stat_row(left, "✅  Success", "0", "#22c55e")
        self._duplicate_lbl = self._stat_row(left, "⚠️  Duplicate", "0", "#f59e0b")
        self._failed_lbl = self._stat_row(left, "❌  Failed", "0", "#ef4444")

        ctk.CTkFrame(left, height=1, fg_color="#333333").pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkButton(
            left,
            text="🔁  Retry Failed",
            command=self._vm.retry_failed,
            fg_color="#374151",
            hover_color="#4b5563",
            font=ctk.CTkFont(size=12),
        ).pack(fill="x", padx=16, pady=16)

    def _build_right_panel(self) -> None:
        right = ctk.CTkFrame(self._frame, corner_radius=10, fg_color=("#1a1a2a", "#1a1a2a"))
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right,
            text="Live Feed",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self._idle_label = ctk.CTkLabel(
            right,
            text="Waiting for images in  Sticker/  …",
            font=ctk.CTkFont(size=15),
            text_color="#444444",
        )
        self._idle_label.grid(row=1, column=0)

        self._status_bar = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
            anchor="w",
        )
        self._status_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

    @staticmethod
    def _stat_row(parent, label: str, value: str, color: str) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(row, text=label, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        val_lbl = ctk.CTkLabel(
            row, text=value, anchor="e",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=color,
        )
        val_lbl.pack(side="right")
        return val_lbl

    # ------------------------------------------------------------------ #
    # ViewModel bindings (all callbacks must use .after(0, ...) because  #
    # they may be called from background threads)                         #
    # ------------------------------------------------------------------ #

    def _bind_vm_events(self) -> None:
        def _after(fn):
            def wrapper(data):
                self._frame.after(0, lambda d=data: fn(d))
            return wrapper

        self._vm.subscribe(Event.USB_STATUS_CHANGED, _after(self._refresh_usb))
        self._vm.subscribe(Event.STATS_UPDATED, _after(self._refresh_stats))
        self._vm.subscribe(Event.QUEUE_UPDATED, _after(self._refresh_queue))
        self._vm.subscribe(Event.JOB_STARTED, _after(self._on_job_started))
        self._vm.subscribe(Event.JOB_COMPLETED, _after(self._on_job_completed))
        self._vm.subscribe(Event.PREVIEW_READY, _after(self._on_preview_ready))

    def _refresh_usb(self, path) -> None:
        if path:
            self._usb_icon.configure(text="💾  Connected", text_color="#22c55e")
            self._usb_label.configure(text=str(path))
        else:
            self._usb_icon.configure(text="⚠️  Not Detected", text_color="#f59e0b")
            self._usb_label.configure(text="Insert USB drive to continue")

    def _refresh_stats(self, stats: dict) -> None:
        self._success_lbl.configure(text=str(stats.get("success", 0)))
        self._duplicate_lbl.configure(text=str(stats.get("duplicate", 0)))
        self._failed_lbl.configure(text=str(stats.get("failed", 0)))

    def _refresh_queue(self, pending: int) -> None:
        self._pending_lbl.configure(text=str(pending))

    def _on_job_started(self, job: ProcessingJob) -> None:
        self._processing_lbl.configure(text=job.image_path.name)
        self._status_bar.configure(text=f"⚙️  Running OCR on {job.image_path.name} …")
        self._idle_label.grid_remove()

    def _on_job_completed(self, job: ProcessingJob) -> None:
        self._processing_lbl.configure(text="—")
        color = job.status.color()
        self._status_bar.configure(
            text=f"{job.status.label()}  —  {job.folder_name or job.image_path.name}",
            text_color=color,
        )
        if self._vm.pending_count == 0 and self._vm.current_job is None:
            self._idle_label.grid()

    def _on_preview_ready(self, data: dict) -> None:
        job: ProcessingJob = data["job"]
        ocr: OCRResult = data["ocr"]

        if self._preview_dialog and self._preview_dialog.is_alive():
            self._preview_dialog.close()

        self._preview_dialog = PreviewDialog(
            parent=self._frame.winfo_toplevel(),
            job=job,
            ocr_result=ocr,
            on_confirm=self._vm.submit_preview,
            on_cancel=self._vm.cancel_preview,
        )


class PreviewDialog:
    """
    Modal dialog shown before creating a folder.
    Displays the sticker image, pre-fills OCR values, and allows editing.
    Blocks the worker thread via ViewModel.submit_preview / cancel_preview.
    """

    def __init__(
        self,
        parent,
        job: ProcessingJob,
        ocr_result: OCRResult,
        on_confirm,
        on_cancel,
    ) -> None:
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._closed = False

        self._win = ctk.CTkToplevel(parent)
        self._win.title("Preview — Confirm OCR Result")
        self._win.geometry("960x930")
        self._win.minsize(750, 750)
        self._win.resizable(True, True)
        self._win.attributes("-topmost", True)
        self._win.grab_set()

        self._win.protocol("WM_DELETE_WINDOW", self._skip)

        self._build(job, ocr_result)
        self._win.focus_force()

    def _build(self, job: ProcessingJob, ocr: OCRResult) -> None:
        self._job = job
        # Image preview frame
        img_container = ctk.CTkFrame(self._win, fg_color="transparent")
        img_container.pack(fill="both", expand=True, padx=16, pady=(12, 4))

        self._img_label = ctk.CTkLabel(img_container, text="", width=_PREVIEW_W, height=_PREVIEW_H)
        self._img_label.pack(fill="both", expand=True)
        self._img_label.bind("<Button-1>", lambda _e: ImageZoomWindow(self._win, job.image_path))
        self._load_preview_image(job.image_path)

        # Filename label & Zoom hint
        info_row = ctk.CTkFrame(self._win, fg_color="transparent")
        info_row.pack(fill="x", padx=28, pady=(0, 4))

        ctk.CTkLabel(
            info_row,
            text=f"📄  {job.image_path.name}",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        ).pack(side="left")

        ctk.CTkButton(
            info_row,
            text="🔍  Zoom Image",
            command=lambda: ImageZoomWindow(self._win, job.image_path),
            fg_color="#1f2937", hover_color="#374151",
            text_color="#60a5fa",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=26,
            width=110,
        ).pack(side="right")

        # Fields
        fields_frame = ctk.CTkFrame(self._win, fg_color="transparent")
        fields_frame.pack(fill="x", padx=28, pady=(4, 0))
        fields_frame.columnconfigure(1, weight=1)

        self._sn_var = ctk.StringVar(value=ocr.serial_number or "")
        self._id_var = ctk.StringVar(value=ocr.device_id or "")
        self._folder_var = ctk.StringVar()

        self._sn_var.trace_add("write", lambda *_: self._update_folder())
        self._id_var.trace_add("write", lambda *_: self._update_folder())

        self._make_field(fields_frame, 0, "S/N:", self._sn_var, "#60a5fa")
        self._make_field(fields_frame, 1, "ID No.:", self._id_var, "#a78bfa")

        ctk.CTkLabel(
            fields_frame, text="Folder:", anchor="w", width=90,
            font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=2, column=0, sticky="w", pady=(8, 4))

        self._folder_label = ctk.CTkLabel(
            fields_frame,
            textvariable=self._folder_var,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f0f0f0",
            anchor="w",
        )
        self._folder_label.grid(row=2, column=1, sticky="w", pady=(8, 4))

        # Validation message — must exist before _update_folder() is called
        self._val_label = ctk.CTkLabel(
            self._win, text="", font=ctk.CTkFont(size=12), text_color="#ef4444"
        )
        self._val_label.pack(pady=(2, 0))

        self._update_folder()

        # Buttons
        btn_row = ctk.CTkFrame(self._win, fg_color="transparent")
        btn_row.pack(pady=(12, 16))

        ctk.CTkButton(
            btn_row, text="✅  Confirm",
            command=self._confirm,
            fg_color="#16a34a", hover_color="#15803d",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            width=160,
        ).pack(side="left", padx=(0, 16))

        ctk.CTkButton(
            btn_row, text="⏭  Skip",
            command=self._skip,
            fg_color="#374151", hover_color="#4b5563",
            font=ctk.CTkFont(size=15),
            height=42,
            width=120,
        ).pack(side="left")

    @staticmethod
    def _make_field(
        parent: ctk.CTkFrame, row: int, label: str, var: ctk.StringVar, accent: str
    ) -> None:
        ctk.CTkLabel(
            parent, text=label, anchor="w", width=90,
            font=ctk.CTkFont(size=15, weight="bold")
        ).grid(
            row=row, column=0, sticky="w", pady=4
        )
        entry = ctk.CTkEntry(
            parent,
            textvariable=var,
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            border_color=accent,
            border_width=2,
            height=40,
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)

    def _update_folder(self) -> None:
        sn = sanitize_filename_str(self._sn_var.get().strip().upper())
        did = sanitize_filename_str(self._id_var.get().strip().upper())

        sn_ok = validate_serial_number(sn) if sn else False
        id_ok = validate_device_id(did) if did else False

        if sn_ok and id_ok:
            name = build_folder_name(sn, did)
            self._folder_var.set(name)
            self._folder_label.configure(text_color="#22c55e")
            self._val_label.configure(text="")
        else:
            parts = []
            if sn and not sn_ok:
                parts.append("S/N must be 8 uppercase alphanumeric characters")
            if did and not id_ok:
                parts.append("ID must match ##S-X### (e.g. 22S-A460)")
            self._folder_var.set("— Invalid format")
            self._folder_label.configure(text_color="#ef4444")
            self._val_label.configure(text=" | ".join(parts))

    def _confirm(self) -> None:
        sn = sanitize_filename_str(self._sn_var.get().strip().upper())
        did = sanitize_filename_str(self._id_var.get().strip().upper())
        if not validate_serial_number(sn) or not validate_device_id(did):
            self._val_label.configure(text="Fix validation errors before confirming.")
            return
        self._close()
        self._on_confirm(sn, did)

    def _skip(self) -> None:
        self._close()
        self._on_cancel()

    def _close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._win.grab_release()
                self._win.destroy()
            except Exception:
                pass

    def is_alive(self) -> bool:
        try:
            return self._win.winfo_exists()
        except Exception:
            return False

    def close(self) -> None:
        self._close()

    def _load_preview_image(self, image_path: Path) -> None:
        try:
            img_cv = cv2.imread(str(image_path))
            if img_cv is None:
                self._img_label.configure(text="(cannot load image)")
                return

            img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
            pil_img = PILImage.fromarray(img_rgb)

            # Fit into preview box
            pil_img.thumbnail((_PREVIEW_W, _PREVIEW_H), PILImage.LANCZOS)
            ctk_img = ctk.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=pil_img.size,
            )
            self._img_label.configure(image=ctk_img, text="")
            self._img_label._image = ctk_img  # keep reference alive
        except Exception as exc:
            logger.warning("Could not load preview image: %s", exc)
            self._img_label.configure(text="(preview unavailable)")
