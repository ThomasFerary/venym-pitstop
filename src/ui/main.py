"""
Venym Pitstop — Main Window
"""

import struct
import time as _time
import tkinter as tk
import customtkinter as ctk

from ..core.config import (FullConfig, PedalConfig, ResponseCurve, CurvePoint,
                           GlobalSettings, PedalLedConfig, LedColor)
from ..usb.protocol import (FeatureReport, PedalReport, Pedal, PEDAL_TO_REPORT,
                                fw_y1_to_output_pct, output_pct_to_fw_y1,
                                CurvePoint as FwCurvePoint)
from ..core.profile import ProfileManager
from ..usb.device import VenymDevice, ConnectionState
from .curve_editor import CurveEditor
from .i18n import t, set_lang, get_lang

# ── Theme ──────────────────────────────────────────────
BG          = "#000000"
CARD_BG     = "#0E131B"
BORDER      = "#202530"
LABEL_CLR   = "#5C6678"
TEXT_CLR    = "#D3E4FF"
PAD         = 15
GAP         = 15
BTN_FONT    = ("", 11, "bold")
LABEL_FONT  = ("", 10)
VALUE_FONT  = ("", 10, "bold")
TITLE_FONT  = ("", 14, "bold")
PCT_FONT    = ("", 20, "bold")


# ── PedalPanel ─────────────────────────────────────────
class PedalPanel(ctk.CTkFrame):

    def __init__(self, master, name: str, color: str, is_brake: bool = False,
                 has_led: bool = False, **kwargs):
        kwargs.setdefault("fg_color", CARD_BG)
        kwargs.setdefault("border_color", BORDER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)

        self.pedal_name = name
        self.color = color
        self.is_brake = is_brake
        self.has_led = has_led
        self._value = 0.0
        self._led_config: PedalLedConfig | None = None
        self._on_led_change_cb = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
        ctk.CTkLabel(header, text=name, font=TITLE_FONT, text_color=TEXT_CLR).pack(side="left")
        self.value_label = ctk.CTkLabel(header, text="0%", font=PCT_FONT, text_color=color)
        self.value_label.pack(side="right")

        # ── Curve + bar ──
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(GAP // 2, 0))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_rowconfigure(0, weight=1)

        self.curve_editor = CurveEditor(mid, width=200, height=200)
        self.curve_editor.CURVE_COLOR = color
        self.curve_editor.PADDING = 20
        self.curve_editor.BG_COLOR = CARD_BG
        self.curve_editor.GRID_COLOR = BORDER
        self.curve_editor.configure(bg=CARD_BG)
        self.curve_editor.grid(row=0, column=0, sticky="nsew")

        # ── LED color indicators (right side of curve) ──
        bar_frame = ctk.CTkFrame(mid, fg_color="transparent")
        bar_frame.grid(row=0, column=1, sticky="ns", padx=(GAP // 2, 0))

        if has_led:
            # Color button for 100% (max) — disabled, firmware protocol unknown
            self.led_max_btn = tk.Canvas(bar_frame, width=22, height=22,
                                          bg=color, highlightthickness=1,
                                          highlightbackground="#333333")
            self.led_max_btn.pack(pady=(0, 4))
            # Dimmed overlay to indicate disabled
            self.led_max_btn.create_rectangle(0, 0, 22, 22, fill="", outline="",
                                               stipple="gray50")

        self.bar_canvas = tk.Canvas(bar_frame, width=24, bg=CARD_BG, highlightthickness=0)
        self.bar_canvas.pack(fill="y", expand=True)

        if has_led:
            # Color button for 0% (min/rest) — disabled, firmware protocol unknown
            self.led_min_btn = tk.Canvas(bar_frame, width=22, height=22,
                                          bg="#000000", highlightthickness=1,
                                          highlightbackground="#333333")
            self.led_min_btn.pack(pady=(4, 0))

        # ── Settings ──
        settings = ctk.CTkFrame(self, fg_color="transparent")
        settings.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(GAP // 2, PAD))
        settings.grid_columnconfigure(2, weight=1)

        BW, BH = 28, 26

        # DZ basse
        ctk.CTkLabel(settings, text=t("dz_low"), font=LABEL_FONT,
                      text_color=LABEL_CLR, anchor="w").grid(row=0, column=0, sticky="w", pady=2)
        ctk.CTkButton(settings, text="-", width=BW, height=BH, font=BTN_FONT,
                       command=lambda: self._dz_low_step(-0.5)).grid(row=0, column=1, padx=(10, 5), pady=2)
        self.dz_low_label = ctk.CTkLabel(settings, text="0.0%", font=VALUE_FONT, text_color=TEXT_CLR)
        self.dz_low_label.grid(row=0, column=2, pady=2)
        ctk.CTkButton(settings, text="+", width=BW, height=BH, font=BTN_FONT,
                       command=lambda: self._dz_low_step(0.5)).grid(row=0, column=3, padx=(5, 0), pady=2)

        # DZ haute
        ctk.CTkLabel(settings, text=t("dz_high"), font=LABEL_FONT,
                      text_color=LABEL_CLR, anchor="w").grid(row=1, column=0, sticky="w", pady=2)
        ctk.CTkButton(settings, text="-", width=BW, height=BH, font=BTN_FONT,
                       command=lambda: self._dz_high_step(-0.5)).grid(row=1, column=1, padx=(10, 5), pady=2)
        self.dz_high_label = ctk.CTkLabel(settings, text="0.0%", font=VALUE_FONT, text_color=TEXT_CLR)
        self.dz_high_label.grid(row=1, column=2, pady=2)
        ctk.CTkButton(settings, text="+", width=BW, height=BH, font=BTN_FONT,
                       command=lambda: self._dz_high_step(0.5)).grid(row=1, column=3, padx=(5, 0), pady=2)

        # Force (brake) / placeholder
        if is_brake:
            ctk.CTkLabel(settings, text=t("force"), font=LABEL_FONT,
                          text_color=LABEL_CLR, anchor="w").grid(row=2, column=0, sticky="w", pady=2)
            ctk.CTkButton(settings, text="-", width=BW, height=BH, font=BTN_FONT,
                           command=lambda: self._force_step(-1)).grid(row=2, column=1, padx=(10, 5), pady=2)
            self.force_label = ctk.CTkLabel(settings, text="0 kg", font=VALUE_FONT, text_color=TEXT_CLR)
            self.force_label.grid(row=2, column=2, pady=2)
            ctk.CTkButton(settings, text="+", width=BW, height=BH, font=BTN_FONT,
                           command=lambda: self._force_step(1)).grid(row=2, column=3, padx=(5, 0), pady=2)
        else:
            ctk.CTkLabel(settings, text="", height=BH).grid(row=2, column=0, columnspan=4, pady=2)

        # State
        self._pedal_config: PedalConfig | None = None
        self._on_curve_change_cb = None
        self.curve_editor._on_change = self._on_curve_changed

    # ── Public ──

    def bind_config(self, config: PedalConfig, on_curve_change=None):
        self._pedal_config = config
        self._on_curve_change_cb = on_curve_change
        self.refresh()

    def refresh(self):
        cfg = self._pedal_config
        if not cfg:
            return
        self.curve_editor.set_curve(cfg.curve)
        self.dz_low_label.configure(text=f"{cfg.fw_param_a / 100:.1f}%")
        self.dz_high_label.configure(text=f"{cfg.dead_zone_high:.1f}%")
        if self.is_brake:
            self.force_label.configure(text=f"{cfg.fw_param_b / 100:.1f} kg")

    def update_value(self, ratio: float):
        self._value = max(0.0, min(1.0, ratio))
        self.value_label.configure(text=f"{self._value * 100:.0f}%")
        self._draw_bar()

    # ── Private ──

    def _draw_bar(self):
        c = self.bar_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 4 or h < 4:
            return
        c.create_rectangle(1, 1, w - 1, h - 1, fill="#0A0E14", outline=BORDER)
        bar_h = int((h - 4) * self._value)
        if bar_h > 0:
            c.create_rectangle(3, h - 3 - bar_h, w - 3, h - 3, fill=self.color, outline="")

    def _on_curve_changed(self, curve):
        if self._pedal_config:
            self._pedal_config.curve = curve
            if self._on_curve_change_cb:
                self._on_curve_change_cb(self._pedal_config)

    def _dz_low_step(self, delta):
        if not self._pedal_config:
            return
        cfg = self._pedal_config
        new_pct = max(0.5, min(20.0, cfg.fw_param_a / 100.0 + delta))
        cfg.fw_param_a = int(round(new_pct * 100))
        self.dz_low_label.configure(text=f"{new_pct:.1f}%")

    def _dz_high_step(self, delta):
        if not self._pedal_config:
            return
        cfg = self._pedal_config
        new_dz = max(0.0, min(20.0, cfg.dead_zone_high + delta))
        cfg.dead_zone_high = new_dz
        self.dz_high_label.configure(text=f"{new_dz:.1f}%")

    def _force_step(self, delta_kg):
        if not self._pedal_config or not self.is_brake:
            return
        cfg = self._pedal_config
        current_kg = cfg.fw_param_b / 100.0
        new_kg = max(1.0, min(100.0, current_kg + delta_kg))
        cfg.fw_param_b = int(round(new_kg * 100))
        self.force_label.configure(text=f"{new_kg:.1f} kg")

    # ── LED ──

    def bind_led_config(self, led_config: PedalLedConfig, on_change=None):
        self._led_config = led_config
        self._on_led_change_cb = on_change
        if self.has_led:
            self.led_max_btn.configure(bg=led_config.color_max.to_hex())
            self.led_min_btn.configure(bg=led_config.color_min.to_hex())

    def _pick_led_color(self, which: str):
        from tkinter import colorchooser
        if not self._led_config:
            return
        current = self._led_config.color_max if which == "max" else self._led_config.color_min
        result = colorchooser.askcolor(color=current.to_hex(), title=f"LED {which}")
        if result and result[1]:
            new_color = LedColor.from_hex(result[1])
            if which == "max":
                self._led_config.color_max = new_color
                self.led_max_btn.configure(bg=new_color.to_hex())
            else:
                self._led_config.color_min = new_color
                self.led_min_btn.configure(bg=new_color.to_hex())
            if self._on_led_change_cb:
                self._on_led_change_cb(self._led_config)


# ── Main Window ────────────────────────────────────────
class VenymPitstop(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title(t("app_title"))
        self.geometry("1250x780")
        self.minsize(1000, 650)
        self.configure(fg_color=BG)

        ctk.set_appearance_mode("dark")

        # State
        self.config = FullConfig.default()
        self.profiles = ProfileManager()
        self.device = VenymDevice()
        self.device.on_state_change(self._on_connection_change)
        self._calibrating = False
        self._device_name = ""

        self._vjoy_available = False

        self._build_ui()
        self._set_connected_ui(False)
        self._poll_device()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_global_settings()
        self._build_panels()
        self._build_footer()

    # ── Header ──

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER,
                               border_width=1, corner_radius=8)
        header.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
        header.grid_columnconfigure(1, weight=1)

        # Left: device info
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.grid(row=0, column=0, sticky="w", padx=PAD, pady=PAD)

        self.status_label = ctk.CTkLabel(info, text=t("no_device"),
                                          font=("", 13, "bold"), text_color=TEXT_CLR)
        self.status_label.pack(anchor="w")

        self.time_label = ctk.CTkLabel(info, text="",
                                        font=("", 10), text_color=LABEL_CLR)
        self.time_label.pack(anchor="w")

        # Right: buttons
        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.grid(row=0, column=2, sticky="e", padx=PAD, pady=PAD)

        self.connect_btn = ctk.CTkButton(btns, text=t("connect"), width=110, height=32,
                                          font=BTN_FONT, command=self._on_connect)
        self.connect_btn.pack(side="left", padx=(0, 10))

        self.send_btn = ctk.CTkButton(btns, text=t("send"), width=160, height=32,
                                       font=BTN_FONT, fg_color="#cc6600", hover_color="#e07700",
                                       command=self._on_send_to_device)
        self.send_btn.pack(side="left")

        lang_label = "EN" if get_lang() == "fr" else "FR"
        self.lang_btn = ctk.CTkButton(btns, text=lang_label, width=40, height=32,
                                       font=BTN_FONT, fg_color="#333844", hover_color="#444c5a",
                                       command=self._toggle_lang)
        self.lang_btn.pack(side="left", padx=(10, 0))

    # ── Global Settings ──

    def _build_global_settings(self):
        self._global_frame = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER,
                                            border_width=1, corner_radius=8)
        frame = self._global_frame
        frame.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(GAP, 0))

        DISABLED_CLR = "#3a3a4a"

        # Title + not implemented badge
        title_row = ctk.CTkFrame(frame, fg_color="transparent")
        title_row.pack(fill="x", padx=PAD, pady=(PAD, 5))
        ctk.CTkLabel(title_row, text=t("global_settings"), font=TITLE_FONT,
                      text_color=TEXT_CLR).pack(side="left")
        ctk.CTkLabel(title_row, text=f"  ⚠ {t('not_implemented')}",
                      font=("", 9), text_color="#886622").pack(side="left", padx=(10, 0))

        # Content row
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=PAD, pady=(0, PAD))

        gs = self.config.global_settings

        # Left: inverted pedals checkbox (disabled)
        self._invert_var = ctk.BooleanVar(value=gs.inverted_pedals)
        self._invert_cb = ctk.CTkCheckBox(content, text=t("inverted_pedals"),
                                            variable=self._invert_var, font=LABEL_FONT,
                                            text_color=DISABLED_CLR, state="disabled",
                                            command=self._on_global_change)
        self._invert_cb.pack(side="left", padx=(0, 30))

        # Middle: flicker brake LEDs (disabled)
        self._flicker_var = ctk.BooleanVar(value=gs.flicker_brake_enabled)
        self._flicker_cb = ctk.CTkCheckBox(content, text=t("flicker_brake"),
                                             variable=self._flicker_var, font=LABEL_FONT,
                                             text_color=DISABLED_CLR, state="disabled",
                                             command=self._on_global_change)
        self._flicker_cb.pack(side="left", padx=(0, 5))

        self._flicker_thresh = ctk.CTkEntry(content, width=70, height=28, font=VALUE_FONT,
                                              state="disabled")
        self._flicker_thresh.pack(side="left", padx=(0, 20))

        # LED max intensity (disabled)
        ctk.CTkLabel(content, text=t("led_max_intensity"), font=LABEL_FONT,
                      text_color=DISABLED_CLR).pack(side="left", padx=(0, 5))

        self._intensity_entry = ctk.CTkEntry(content, width=70, height=28, font=VALUE_FONT,
                                               state="disabled")
        self._intensity_entry.pack(side="left", padx=(0, 30))

        # ABS telemetry flicker (second row, disabled)
        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", padx=PAD, pady=(0, PAD))

        self._abs_var = ctk.BooleanVar(value=gs.flicker_abs_telemetry)
        self._abs_cb = ctk.CTkCheckBox(row2, text=t("flicker_abs"),
                                         variable=self._abs_var, font=LABEL_FONT,
                                         text_color=DISABLED_CLR, state="disabled",
                                         command=self._on_global_change)
        self._abs_cb.pack(side="left")

    def _on_global_change(self):
        gs = self.config.global_settings
        gs.inverted_pedals = self._invert_var.get()
        gs.flicker_brake_enabled = self._flicker_var.get()
        gs.flicker_abs_telemetry = self._abs_var.get()

    def _on_flicker_thresh_change(self, event=None):
        text = self._flicker_thresh.get().replace("%", "").strip()
        try:
            val = max(0.0, min(100.0, float(text)))
        except ValueError:
            val = self.config.global_settings.flicker_brake_threshold
        self.config.global_settings.flicker_brake_threshold = val
        self._flicker_thresh.delete(0, "end")
        self._flicker_thresh.insert(0, f"{val:.2f}%")

    def _on_intensity_change(self, event=None):
        text = self._intensity_entry.get().replace("%", "").strip()
        try:
            val = max(0.0, min(100.0, float(text)))
        except ValueError:
            val = self.config.global_settings.led_max_intensity
        self.config.global_settings.led_max_intensity = val
        self._intensity_entry.delete(0, "end")
        self._intensity_entry.insert(0, f"{val:.0f}%")

    def _refresh_global_settings_ui(self):
        """Sync global settings UI with current config values."""
        gs = self.config.global_settings
        self._invert_var.set(gs.inverted_pedals)
        self._flicker_var.set(gs.flicker_brake_enabled)
        self._abs_var.set(gs.flicker_abs_telemetry)
        self._flicker_thresh.delete(0, "end")
        self._flicker_thresh.insert(0, f"{gs.flicker_brake_threshold:.2f}%")
        self._intensity_entry.delete(0, "end")
        self._intensity_entry.insert(0, f"{gs.led_max_intensity:.0f}%")

    # ── Panels ──

    def _build_panels(self):
        self._panels_container = ctk.CTkFrame(self, fg_color="transparent")
        container = self._panels_container
        container.grid(row=2, column=0, sticky="nsew", padx=PAD, pady=GAP)
        container.grid_columnconfigure(0, weight=1, uniform="p")
        container.grid_columnconfigure(1, weight=1, uniform="p")
        container.grid_columnconfigure(2, weight=1, uniform="p")
        container.grid_rowconfigure(0, weight=1)

        self.panels: dict[str, PedalPanel] = {}

        self.panels["clutch"] = PedalPanel(container, t("clutch"), "#3399ff")
        self.panels["clutch"].grid(row=0, column=0, sticky="nsew", padx=(0, GAP // 2))

        self.panels["brake"] = PedalPanel(container, t("brake"), "#cc3333",
                                           is_brake=True, has_led=True)
        self.panels["brake"].grid(row=0, column=1, sticky="nsew", padx=(GAP // 2, GAP // 2))

        self.panels["throttle"] = PedalPanel(container, t("throttle"), "#00cc66", has_led=True)
        self.panels["throttle"].grid(row=0, column=2, sticky="nsew", padx=(GAP // 2, 0))

        self.panels["throttle"].bind_config(self.config.throttle, self._on_curve_change)
        self.panels["brake"].bind_config(self.config.brake, self._on_curve_change)
        self.panels["clutch"].bind_config(self.config.clutch, self._on_curve_change)

        # Bind LED configs
        self.panels["brake"].bind_led_config(self.config.brake_led)
        self.panels["throttle"].bind_led_config(self.config.throttle_led)

    # ── Footer ──

    def _build_footer(self):
        self._footer = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER,
                                      border_width=1, corner_radius=8, height=50)
        footer = self._footer
        footer.grid(row=3, column=0, sticky="ew", padx=PAD, pady=(0, PAD))

        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="x", padx=PAD, pady=PAD)

        ctk.CTkLabel(inner, text=t("profile"), font=LABEL_FONT,
                      text_color=LABEL_CLR).pack(side="left")
        self.profile_combo = ctk.CTkComboBox(
            inner, values=self.profiles.list_profiles() or ["default"],
            width=160, height=30, font=LABEL_FONT)
        self.profile_combo.pack(side="left", padx=(10, 10))

        ctk.CTkButton(inner, text=t("load"), width=80, height=30,
                       font=BTN_FONT, command=self._on_load_profile).pack(side="left", padx=(0, 10))
        ctk.CTkButton(inner, text=t("save"), width=100, height=30,
                       font=BTN_FONT, command=self._on_save_profile).pack(side="left")

        ctk.CTkButton(inner, text=t("calibrate_all"), width=120, height=30,
                       font=BTN_FONT, fg_color="#333844", hover_color="#444c5a",
                       command=self._on_calibrate_all).pack(side="right")

        ctk.CTkButton(inner, text=t("import_backup"), width=130, height=30,
                       font=BTN_FONT, fg_color="#333844", hover_color="#444c5a",
                       command=self._on_import_backup).pack(side="right", padx=(0, 10))

        ctk.CTkButton(inner, text=t("export_backup"), width=130, height=30,
                       font=BTN_FONT, fg_color="#333844", hover_color="#444c5a",
                       command=self._on_export_backup).pack(side="right", padx=(0, 10))

    # ── Connection ──

    def _set_connected_ui(self, connected: bool):
        """Affiche ou masque les elements qui necessitent un pedalier connecte."""
        if connected:
            self._global_frame.grid()
            self._panels_container.grid()
            self._footer.grid()
            self.connect_btn.pack_forget()
            self.send_btn.pack_forget()
            self.lang_btn.pack_forget()
            self.send_btn.pack(side="left", padx=(0, 10))
            self.lang_btn.pack(side="left")
        else:
            self._global_frame.grid_remove()
            self._panels_container.grid_remove()
            self._footer.grid_remove()
            self.send_btn.pack_forget()
            self.connect_btn.pack_forget()
            self.lang_btn.pack_forget()
            self.connect_btn.pack(side="left", padx=(0, 10))
            self.lang_btn.pack(side="left")

    def _on_connection_change(self, state: ConnectionState):
        if state == ConnectionState.CONNECTED:
            name = self._device_name or "Connecte"
            self.status_label.configure(text=name, text_color="#00cc66")
            self._set_connected_ui(True)
        elif state == ConnectionState.DISCONNECTED:
            self.status_label.configure(text=t("disconnected"), text_color=LABEL_CLR)
            self.time_label.configure(text="")
            self._set_connected_ui(False)
        elif state == ConnectionState.CONNECTING:
            self.status_label.configure(text=t("connecting"), text_color="#cccc00")
        elif state == ConnectionState.ERROR:
            self.status_label.configure(text=t("error"), text_color="#cc3333")
            self._set_connected_ui(False)

    def _toggle_lang(self):
        new_lang = "en" if get_lang() == "fr" else "fr"
        set_lang(new_lang)
        # Rebuild UI
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        was_connected = self.device.is_connected
        if was_connected:
            self._set_connected_ui(True)
            # Re-bind panels
            self.panels["throttle"].bind_config(self.config.throttle, self._on_curve_change)
            self.panels["brake"].bind_config(self.config.brake, self._on_curve_change)
            self.panels["clutch"].bind_config(self.config.clutch, self._on_curve_change)
            self.panels["brake"].bind_led_config(self.config.brake_led)
            self.panels["throttle"].bind_led_config(self.config.throttle_led)
            self.status_label.configure(text=self._device_name, text_color="#00cc66")
        else:
            self._set_connected_ui(False)

    def _on_connect(self):
        devices = VenymDevice.find_venym_devices()
        if not devices:
            self.status_label.configure(text=t("no_device_found"), text_color="#cc3333")
            return
        info = devices[0]
        self._device_name = info.product_string or f"Venym {info.vid_pid_str}"
        if not self.device.connect(info.vendor_id, info.product_id):
            self.status_label.configure(text=t("connect_failed"), text_color="#cc3333")
            return
        self._load_device_config()
        self.device.start_auto_reconnect(info.vendor_id, info.product_id)

    def _load_device_config(self):
        # Time meter
        r03 = self.device.get_feature_report(0x03)
        if r03 and len(r03) >= 4:
            r03b = bytes(r03)
            secs = r03b[1] | (r03b[2] << 8) | (r03b[3] << 16)
            self.time_label.configure(text=t("time_meter", h=secs // 3600, m=(secs % 3600) // 60))

        pedal_mapping = [
            (Pedal.THROTTLE, self.config.throttle, "throttle"),
            (Pedal.BRAKE, self.config.brake, "brake"),
            (Pedal.CLUTCH, self.config.clutch, "clutch"),
        ]

        loaded = 0
        for pedal, cfg, key in pedal_mapping:
            data = self.device.get_feature_report(PEDAL_TO_REPORT[pedal])
            if not data or len(data) < 38:
                continue
            try:
                report = PedalReport.from_report(data)
                cfg.cal_min = report.cal_min
                cfg.cal_max = report.cal_max
                cfg.fw_param_a = report.param_a
                cfg.fw_param_b = report.param_b
                cfg.fw_curve_y1 = [pt.y_byte1 for pt in report.curve_points]
                cfg.fw_curve_y2 = [pt.y_byte2 for pt in report.curve_points]

                last_pt = report.curve_points[-1] if report.curve_points else None
                max_out = fw_y1_to_output_pct(last_pt.y_byte1) if last_pt else 1.0
                max_out = max(max_out, 0.001)

                if last_pt:
                    cfg.dead_zone_high = last_pt.y_byte2 / 32.0
                else:
                    cfg.dead_zone_high = 0.0

                pts = [CurvePoint(0.0, 0.0)]
                for i, pt in enumerate(report.curve_points):
                    if i == len(report.curve_points) - 1:
                        pts.append(CurvePoint(1.0, 1.0))
                    else:
                        pts.append(CurvePoint(
                            max(0.0, min(1.0, pt.x_pct / 100.0)),
                            max(0.0, min(1.0, fw_y1_to_output_pct(pt.y_byte1) / max_out))))
                cfg.curve = ResponseCurve(pts)

                self.panels[key].bind_config(cfg, self._on_curve_change)
                loaded += 1

                fw = " ".join(f"({pt.x_pct},{pt.y_byte1},{pt.y_byte2})" for pt in report.curve_points)
                print(f"  {cfg.name}: cal={report.cal_min}-{report.cal_max} "
                      f"pa={report.param_a} pb={report.param_b} fw=[{fw}]")
            except (ValueError, struct.error) as e:
                print(f"  Erreur {pedal.name}: {e}")

        if loaded > 0:
            self.status_label.configure(text=self._device_name, text_color="#00cc66")

    # ── Curve change ──

    def _on_curve_change(self, pedal_cfg: PedalConfig):
        max_y1 = pedal_cfg.fw_curve_y1[-1] if pedal_cfg.fw_curve_y1 else 86
        new_y1 = []
        for x in [20, 40, 60, 80]:
            y = pedal_cfg.curve.evaluate(x / 100.0)
            new_y1.append(output_pct_to_fw_y1(y * fw_y1_to_output_pct(max_y1)))
        new_y1.append(max_y1)
        pedal_cfg.fw_curve_y1 = new_y1

    # ── Send ──

    def _on_send_to_device(self):
        if not self.device.is_connected:
            self.status_label.configure(text=t("not_connected"), text_color="#cc3333")
            return

        from ..usb.protocol import write_pedal_config

        sent = 0
        for pedal, cfg in [(Pedal.THROTTLE, self.config.throttle),
                            (Pedal.BRAKE, self.config.brake),
                            (Pedal.CLUTCH, self.config.clutch)]:
            data = self.device.get_feature_report(PEDAL_TO_REPORT[pedal])
            if not data or len(data) < 38:
                continue
            try:
                report = PedalReport.from_report(data)
                report.cal_min = cfg.cal_min
                report.cal_max = cfg.cal_max
                report.param_a = cfg.fw_param_a
                report.param_b = cfg.fw_param_b

                y1s = cfg.fw_curve_y1
                y2s = list(cfg.fw_curve_y2)
                y2s[4] = max(0, min(255, int(round(cfg.dead_zone_high * 32))))

                report.curve_points = [
                    FwCurvePoint(x_pct=x, y_byte1=y1s[i] if i < len(y1s) else 86,
                                 y_byte2=y2s[i] if i < len(y2s) else 0)
                    for i, x in enumerate([20, 40, 60, 80, 100])
                ]

                if write_pedal_config(self.device, pedal, report):
                    sent += 1
                    fw = " ".join(f"({p.x_pct},{p.y_byte1},{p.y_byte2})" for p in report.curve_points)
                    print(f"  Envoye {cfg.name}: pa={report.param_a} pb={report.param_b} fw=[{fw}]")
            except Exception as e:
                print(f"  Erreur {cfg.name}: {e}")

        if sent:
            self.status_label.configure(text=t("config_sent", n=sent), text_color="#00cc66")

    # ── Profiles ──

    def _on_load_profile(self):
        name = self.profile_combo.get()
        try:
            self.config = self.profiles.load(name)
            for k in ["throttle", "brake", "clutch"]:
                self.panels[k].bind_config(getattr(self.config, k), self._on_curve_change)
            self.panels["brake"].bind_led_config(self.config.brake_led)
            self.panels["throttle"].bind_led_config(self.config.throttle_led)
            self._refresh_global_settings_ui()
            self.status_label.configure(text=t("profile_loaded", name=name), text_color="#00cc66")
        except FileNotFoundError:
            self.status_label.configure(text=t("profile_not_found"), text_color="#cc3333")

    def _on_save_profile(self):
        name = self.profile_combo.get()
        self.profiles.save(name, self.config)
        self.profile_combo.configure(values=self.profiles.list_profiles())
        self.status_label.configure(text=t("profile_saved", name=name), text_color="#00cc66")

    # ── Calibration ──

    def _on_calibrate_all(self):
        if self._calibrating:
            for key in ["throttle", "brake"]:
                dmin = self._cal_min.get(key)
                dmax = self._cal_max.get(key)
                if dmin is not None and dmax is not None and dmax > dmin:
                    cfg = getattr(self.config, key)
                    cfg.cal_min = int(dmin)
                    cfg.cal_max = int(dmax)
                    print(f"  Calibre {key}: cal_min={cfg.cal_min} cal_max={cfg.cal_max}")
            self._calibrating = False
            self._on_send_to_device()
            for k in ["throttle", "brake", "clutch"]:
                self.panels[k].refresh()
            self.status_label.configure(text=t("calibration_done"), text_color="#00cc66")
        else:
            self._cal_min = {"throttle": float("inf"), "brake": float("inf")}
            self._cal_max = {"throttle": float("-inf"), "brake": float("-inf")}
            self._calibrating = True
            self.status_label.configure(text=t("calibrating"), text_color="#cccc00")

    # ── Backup export/import ──

    def _on_export_backup(self):
        """Exporte les Feature Reports bruts du pedalier dans un fichier JSON."""
        if not self.device.is_connected:
            self.status_label.configure(text=t("not_connected"), text_color="#cc3333")
            return

        from tkinter import filedialog
        import json

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="venym-backup.json",
            title=t("export_dialog_title"))
        if not path:
            return

        reports = {}
        for rid in [0x03, 0x05, 0x10, 0x11, 0x12]:
            data = self.device.get_feature_report(rid)
            if data:
                reports[f"0x{rid:02x}"] = {
                    "size": len(data),
                    "raw": list(bytes(data)),
                }

        backup = {
            "device": self._device_name,
            "timestamp": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "reports": reports,
        }

        with open(path, "w") as f:
            json.dump(backup, f, indent=2)

        self.status_label.configure(text=t("backup_exported"), text_color="#00cc66")
        print(f"  Backup exporte: {path}")

    def _on_import_backup(self):
        """Restaure les Feature Reports depuis un fichier JSON."""
        if not self.device.is_connected:
            self.status_label.configure(text=t("not_connected"), text_color="#cc3333")
            return

        from tkinter import filedialog, messagebox
        import json

        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")],
            title=t("import_dialog_title"))
        if not path:
            return

        try:
            with open(path) as f:
                backup = json.load(f)
        except Exception as e:
            self.status_label.configure(text=t("file_invalid"), text_color="#cc3333")
            return

        if "reports" not in backup:
            self.status_label.configure(text=t("backup_invalid"), text_color="#cc3333")
            return

        confirm = messagebox.askyesno(
            t("restore_confirm_title"),
            t("restore_confirm_msg",
              device=backup.get('device', '?'),
              time=backup.get('timestamp', '?')))
        if not confirm:
            return

        from ..usb.protocol import write_pedal_config

        restored = 0
        for rid_str, rid_int in [("0x10", 0x10), ("0x11", 0x11), ("0x12", 0x12)]:
            if rid_str not in backup["reports"]:
                continue
            raw = bytes(backup["reports"][rid_str]["raw"])

            payload = bytearray(63)
            payload[0] = rid_int
            for i, b in enumerate(raw[:min(len(raw), 62)]):
                payload[1 + i] = b
            self.device.send_feature_report(bytes([rid_int]) + bytes(payload))
            _time.sleep(0.2)
            restored += 1

        if restored:
            self._load_device_config()
            self.status_label.configure(text=t("backup_restored", n=restored), text_color="#00cc66")
            print(f"  Backup restaure depuis: {path}")

    # ── Polling ──

    def _poll_device(self):
        if self.device.is_connected:
            data = self.device.read_axes()
            if data and len(data) >= 5:
                try:
                    accel, brake = struct.unpack_from("<HH", bytes(data), 1)
                    adc = {"throttle": accel, "brake": brake}

                    # Calibration via r05
                    if self._calibrating:
                        r05 = self.device.get_feature_report(0x05)
                        if r05 and len(r05) >= 4:
                            r05b = bytes(r05)
                            for k, v in [("throttle", struct.unpack_from("<H", r05b, 0)[0]),
                                          ("brake", struct.unpack_from("<H", r05b, 2)[0])]:
                                self._cal_min[k] = min(self._cal_min.get(k, float("inf")), v)
                                self._cal_max[k] = max(self._cal_max.get(k, float("-inf")), v)

                    for key, raw in adc.items():
                        cfg = getattr(self.config, key)
                        cal_range = cfg.cal_max - cfg.cal_min
                        # Floor = repos (cal_min + offset DZ basse)
                        floor = cfg.cal_min + cfg.fw_param_a * 0.231
                        # Ceiling = max firmware (~92% + DZ haute boost)
                        ceiling_pct = min(0.96, 0.92 + cfg.dead_zone_high * 0.02)
                        ceiling = cfg.cal_min + cal_range * ceiling_pct
                        rng = ceiling - floor
                        ratio = max(0.0, min(1.0, (raw - floor) / rng)) if rng > 0 else 0.0

                        self.panels[key].update_value(ratio)
                        self.panels[key].curve_editor.set_preview(ratio)

                except struct.error:
                    pass

        self.after(16, self._poll_device)


def main():
    app = VenymPitstop()
    app.mainloop()


if __name__ == "__main__":
    main()
