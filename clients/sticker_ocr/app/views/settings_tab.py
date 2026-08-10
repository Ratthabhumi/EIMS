import customtkinter as ctk

from app.config import AppConfig
from app.constants import Event
from app.viewmodels.app_viewmodel import AppViewModel


class SettingsTab:
    """Editable settings panel that writes back to config.json on save."""

    def __init__(self, parent: ctk.CTkFrame, viewmodel: AppViewModel) -> None:
        self._vm = viewmodel
        self._frame = parent
        self._vars: dict = {}

        self._build()
        self._load_values(viewmodel.config)

        self._vm.subscribe(
            Event.CONFIG_CHANGED,
            lambda cfg: self._frame.after(0, lambda: self._load_values(cfg)),
        )

    def _build(self) -> None:
        self._frame.columnconfigure(0, weight=1)
        self._frame.rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self._frame, corner_radius=8)
        scroll.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        scroll.columnconfigure(1, weight=1)

        self._scroll = scroll
        self._row_idx = 0

        self._section("📁  Folders")
        self._text_field("sticker_folder", "Watch Folder")
        self._text_field("processed_folder", "Processed Folder")
        self._text_field("failed_folder", "Failed Folder")
        self._text_field("log_folder", "Log Folder")

        self._section("🔍  OCR")
        self._text_field("ocr_language", "Language Code", hint="en / ch / japan ...")
        self._switch_field("ocr_use_gpu", "Use GPU")
        self._switch_field("crop_enabled", "Auto Crop Sticker")
        self._int_field("crop_padding", "Crop Padding (px)")

        self._section("🖥️  Display")
        self._option_field("theme", "Theme", ["dark", "light", "system"])
        self._int_field("large_display_font_size", "Large Display Font Size")
        self._text_field("large_display_hotkey", "Large Display Hotkey")

        self._section("🔔  Notifications")
        self._switch_field("notification_enabled", "Enable Notifications")

        # Save / Reset buttons
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.grid(
            row=self._row_idx, column=0, columnspan=2,
            sticky="ew", pady=(20, 8), padx=8,
        )

        ctk.CTkButton(
            btn_row, text="💾  Save Settings",
            command=self._save,
            fg_color="#2563eb", hover_color="#1d4ed8",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_row, text="↺  Reset Defaults",
            command=self._reset,
            fg_color="#3a3a3a", hover_color="#555555",
        ).pack(side="left")

    # ------------------------------------------------------------------ #
    # Field helpers                                                       #
    # ------------------------------------------------------------------ #

    def _section(self, title: str) -> None:
        ctk.CTkLabel(
            self._scroll,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(
            row=self._row_idx, column=0, columnspan=2,
            sticky="w", padx=8, pady=(18, 4),
        )
        self._row_idx += 1

    def _text_field(self, key: str, label: str, hint: str = "") -> None:
        ctk.CTkLabel(
            self._scroll, text=label, anchor="w", width=220
        ).grid(row=self._row_idx, column=0, sticky="w", padx=8, pady=4)

        var = ctk.StringVar()
        entry = ctk.CTkEntry(self._scroll, textvariable=var, placeholder_text=hint)
        entry.grid(row=self._row_idx, column=1, sticky="ew", padx=8, pady=4)
        self._vars[key] = ("str", var)
        self._row_idx += 1

    def _int_field(self, key: str, label: str) -> None:
        ctk.CTkLabel(
            self._scroll, text=label, anchor="w", width=220
        ).grid(row=self._row_idx, column=0, sticky="w", padx=8, pady=4)

        var = ctk.StringVar()
        entry = ctk.CTkEntry(self._scroll, textvariable=var, width=100)
        entry.grid(row=self._row_idx, column=1, sticky="w", padx=8, pady=4)
        self._vars[key] = ("int", var)
        self._row_idx += 1

    def _switch_field(self, key: str, label: str) -> None:
        ctk.CTkLabel(
            self._scroll, text=label, anchor="w", width=220
        ).grid(row=self._row_idx, column=0, sticky="w", padx=8, pady=4)

        var = ctk.BooleanVar()
        switch = ctk.CTkSwitch(self._scroll, text="", variable=var, onvalue=True, offvalue=False)
        switch.grid(row=self._row_idx, column=1, sticky="w", padx=8, pady=4)
        self._vars[key] = ("bool", var)
        self._row_idx += 1

    def _option_field(self, key: str, label: str, options: list[str]) -> None:
        ctk.CTkLabel(
            self._scroll, text=label, anchor="w", width=220
        ).grid(row=self._row_idx, column=0, sticky="w", padx=8, pady=4)

        var = ctk.StringVar()
        opt = ctk.CTkOptionMenu(self._scroll, variable=var, values=options)
        opt.grid(row=self._row_idx, column=1, sticky="w", padx=8, pady=4)
        self._vars[key] = ("str", var)
        self._row_idx += 1

    # ------------------------------------------------------------------ #
    # Load / Save / Reset                                                 #
    # ------------------------------------------------------------------ #

    def _load_values(self, cfg: AppConfig) -> None:
        data = {
            "sticker_folder": cfg.sticker_folder,
            "processed_folder": cfg.processed_folder,
            "failed_folder": cfg.failed_folder,
            "log_folder": cfg.log_folder,
            "ocr_language": cfg.ocr_language,
            "ocr_use_gpu": cfg.ocr_use_gpu,
            "crop_enabled": cfg.crop_enabled,
            "crop_padding": cfg.crop_padding,
            "notification_enabled": cfg.notification_enabled,
            "theme": cfg.theme,
            "large_display_font_size": cfg.large_display_font_size,
            "large_display_hotkey": cfg.large_display_hotkey,
        }
        for key, (kind, var) in self._vars.items():
            val = data.get(key)
            if val is None:
                continue
            if kind == "int":
                var.set(str(val))
            elif kind == "bool":
                var.set(bool(val))
            else:
                var.set(str(val))

    def _collect(self) -> dict:
        result = {}
        for key, (kind, var) in self._vars.items():
            if kind == "int":
                try:
                    result[key] = int(var.get())
                except ValueError:
                    result[key] = 0
            elif kind == "bool":
                result[key] = bool(var.get())
            else:
                result[key] = var.get()
        return result

    def _save(self) -> None:
        data = self._collect()
        new_cfg = AppConfig(**{
            k: v for k, v in data.items()
            if k in AppConfig.__dataclass_fields__
        })
        self._vm.update_config(new_cfg)
        self._show_toast("Settings saved.")

    def _reset(self) -> None:
        self._vm.update_config(AppConfig())
        self._show_toast("Reset to defaults.")

    def _show_toast(self, msg: str) -> None:
        toast = ctk.CTkLabel(
            self._frame,
            text=f"  {msg}  ",
            font=ctk.CTkFont(size=12),
            fg_color="#22c55e",
            text_color="white",
            corner_radius=6,
        )
        toast.place(relx=0.5, rely=0.97, anchor="s")
        self._frame.after(2500, toast.destroy)
