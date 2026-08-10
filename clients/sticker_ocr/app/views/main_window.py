import logging
from pathlib import Path

import customtkinter as ctk

from app.constants import APP_NAME, APP_VERSION, Event
from app.viewmodels.app_viewmodel import AppViewModel
from app.views.dashboard_tab import DashboardTab
from app.views.history_tab import HistoryTab
from app.views.large_display_window import LargeDisplayWindow
from app.views.settings_tab import SettingsTab

logger = logging.getLogger(__name__)


class MainWindow:
    """Root application window. Owns the tab layout, USB selector, and large-display overlay."""

    def __init__(self, viewmodel: AppViewModel) -> None:
        self._vm = viewmodel
        self._large_display: LargeDisplayWindow | None = None

        ctk.set_appearance_mode(viewmodel.config.theme)
        ctk.set_default_color_theme("blue")

        self._root = ctk.CTk()
        self._root.title(f"{APP_NAME}  v{APP_VERSION}")
        self._root.geometry("1280x820")
        self._root.minsize(960, 640)

        self._build_header()
        self._build_tabs()
        self._bind_keys()

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # Layout                                                              #
    # ------------------------------------------------------------------ #

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self._root, height=48, corner_radius=0, fg_color=("#111827", "#111827"))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=f"  💽  {APP_NAME}",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).pack(side="left", padx=16)

        # USB Status Pill
        self._usb_pill = ctk.CTkLabel(
            header,
            text="⚠️  No USB",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f59e0b",
            anchor="e",
        )
        self._usb_pill.pack(side="right", padx=(8, 16))

        # Manual USB Drive Selector Dropdown
        self._drive_dropdown = ctk.CTkOptionMenu(
            header,
            values=["Auto (Detect)"],
            command=self._on_drive_selected,
            font=ctk.CTkFont(size=12, weight="bold"),
            dropdown_font=ctk.CTkFont(size=12),
            fg_color="#1f2937",
            button_color="#374151",
            button_hover_color="#4b5563",
            width=140,
            height=28,
        )
        self._drive_dropdown.pack(side="right", padx=8)

        ctk.CTkLabel(
            header,
            text="Target Drive:",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af",
            anchor="e",
        ).pack(side="right", padx=(8, 0))

        ctk.CTkLabel(
            header,
            text="F11 = Large Display  ·  ESC = Exit",
            font=ctk.CTkFont(size=11),
            text_color="#4b5563",
            anchor="e",
        ).pack(side="right", padx=16)

        self._vm.subscribe(
            Event.USB_STATUS_CHANGED,
            lambda path: self._root.after(0, lambda p=path: self._update_usb_pill(p)),
        )
        self._vm.subscribe(
            Event.CONFIG_CHANGED,
            lambda _: self._root.after(0, self._bind_keys),
        )

    def _build_tabs(self) -> None:
        self._tabs = ctk.CTkTabview(self._root, corner_radius=8)
        self._tabs.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self._tabs.add("🏠  Dashboard")
        self._tabs.add("📋  History")
        self._tabs.add("⚙️  Settings")

        DashboardTab(
            parent=self._tabs.tab("🏠  Dashboard"),
            viewmodel=self._vm,
        )
        HistoryTab(
            parent=self._tabs.tab("📋  History"),
            viewmodel=self._vm,
        )
        SettingsTab(
            parent=self._tabs.tab("⚙️  Settings"),
            viewmodel=self._vm,
        )

    def _bind_keys(self) -> None:
        hotkey = self._vm.config.large_display_hotkey
        bind_str = f"<{hotkey}>" if not hotkey.startswith("<") else hotkey
        try:
            self._root.bind(bind_str, self._toggle_large_display)
        except Exception:
            self._root.bind("<F11>", self._toggle_large_display)

    # ------------------------------------------------------------------ #
    # Header USB pill & Drive Dropdown                                    #
    # ------------------------------------------------------------------ #

    def _on_drive_selected(self, choice: str) -> None:
        if choice.startswith("Auto"):
            self._vm.set_manual_usb_drive(None)
        else:
            clean_drive = choice.split()[0].strip()
            self._vm.set_manual_usb_drive(Path(clean_drive))

    def _update_usb_pill(self, path: Path | None) -> None:
        # Update dropdown items list
        drives = self._vm.get_available_usb_drives()
        options = ["Auto (Detect)"] + [f"{d}" for d in drives]
        self._drive_dropdown.configure(values=options)

        if path:
            self._usb_pill.configure(
                text=f"💾  {path}",
                text_color="#22c55e",
            )
        else:
            self._usb_pill.configure(
                text="⚠️  No USB",
                text_color="#f59e0b",
            )

    # ------------------------------------------------------------------ #
    # Large Display overlay & Shutdown                                   #
    # ------------------------------------------------------------------ #

    def _toggle_large_display(self, _event=None) -> None:
        if self._large_display and self._large_display.is_alive():
            self._large_display.close()
            self._large_display = None
        else:
            self._large_display = LargeDisplayWindow(self._root, self._vm)

    def _on_close(self) -> None:
        logger.info("Main window closing")
        if self._large_display and self._large_display.is_alive():
            self._large_display.close()
        self._vm.stop()
        self._root.destroy()

    def run(self) -> None:
        self._vm.start()
        self._root.mainloop()
