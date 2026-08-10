import customtkinter as ctk
from typing import Optional

from app.constants import Event
from app.viewmodels.app_viewmodel import AppViewModel


class LargeDisplayWindow:
    """
    Fullscreen overlay showing S/N and ID in a very large font.
    Opened with F11 (or custom hotkey); closed with ESC or hotkey again.
    """

    def __init__(
        self,
        parent: ctk.CTk,
        viewmodel: AppViewModel,
    ) -> None:
        self._vm = viewmodel
        self._window = ctk.CTkToplevel(parent)
        self._window.title("Large Display")
        self._window.attributes("-fullscreen", True)
        self._window.attributes("-topmost", True)
        self._window.configure(fg_color="#0a0a0a")

        hotkey_raw = self._vm.config.large_display_hotkey
        hotkey = f"<{hotkey_raw}>" if not hotkey_raw.startswith("<") else hotkey_raw
        self._window.bind("<Escape>", lambda _: self.close())
        try:
            self._window.bind(hotkey, lambda _: self.close())
        except Exception:
            self._window.bind("<F11>", lambda _: self.close())

        self._outer = ctk.CTkFrame(self._window, fg_color="transparent")
        self._outer.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self._window,
            text=f"ESC or {hotkey_raw}  ·  Exit Large Display",
            font=ctk.CTkFont(size=14),
            text_color="#444444",
        ).place(relx=0.5, rely=0.95, anchor="center")

        self._render_current()
        self._vm.subscribe(
            Event.JOB_COMPLETED,
            lambda job: self._window.after(0, self._render_current),
        )
        self._vm.subscribe(
            Event.HISTORY_UPDATED,
            lambda _: self._window.after(0, self._render_current),
        )
        self._window.focus_force()

    def _render_current(self) -> None:
        if not self.is_alive():
            return
        for child in self._outer.winfo_children():
            child.destroy()

        font_size = self._vm.config.large_display_font_size
        history = self._vm.history
        sn, device_id = None, None
        if history:
            latest = history[0]
            sn = latest.serial_number
            device_id = latest.device_id
        elif self._vm.current_job:
            sn = self._vm.current_job.serial_number
            device_id = self._vm.current_job.device_id

        if sn:
            ctk.CTkLabel(
                self._outer,
                text=sn,
                font=ctk.CTkFont(family="Consolas", size=font_size, weight="bold"),
                text_color="#f0f0f0",
            ).pack(pady=(0, 16))
        else:
            ctk.CTkLabel(
                self._outer,
                text="No data yet",
                font=ctk.CTkFont(size=max(20, font_size // 2)),
                text_color="#555555",
            ).pack(pady=(0, 16))

        if device_id:
            ctk.CTkLabel(
                self._outer,
                text=f"({device_id})",
                font=ctk.CTkFont(family="Consolas", size=font_size, weight="bold"),
                text_color="#60a5fa",
            ).pack()

    def close(self) -> None:
        try:
            self._window.destroy()
        except Exception:
            pass

    def is_alive(self) -> bool:
        try:
            return self._window.winfo_exists()
        except Exception:
            return False
