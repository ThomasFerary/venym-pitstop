"""
Venym Pitstop — Pedal Widget

Widget CustomTkinter affichant l'état temps réel d'une pédale :
- Barre de progression (valeur brute)
- Barre de progression (valeur après courbe)
- Valeur numérique en %
"""

import customtkinter as ctk


class PedalWidget(ctk.CTkFrame):
    """Widget d'affichage temps réel pour une pédale."""

    def __init__(self, master, name: str, color: str = "#00cc66", **kwargs):
        super().__init__(master, **kwargs)

        self._name = name
        self._raw_value = 0.0
        self._output_value = 0.0

        # Layout
        self.grid_columnconfigure(1, weight=1)

        # Nom de la pédale
        self.label_name = ctk.CTkLabel(self, text=name, font=("", 14, "bold"), width=100, anchor="w")
        self.label_name.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=5)

        # Barre brute
        self.bar_raw = ctk.CTkProgressBar(self, progress_color="gray60", height=12)
        self.bar_raw.grid(row=0, column=1, padx=5, pady=(5, 2), sticky="ew")
        self.bar_raw.set(0)

        # Barre après courbe
        self.bar_output = ctk.CTkProgressBar(self, progress_color=color, height=16)
        self.bar_output.grid(row=1, column=1, padx=5, pady=(2, 5), sticky="ew")
        self.bar_output.set(0)

        # Valeur numérique
        self.label_value = ctk.CTkLabel(self, text="0%", font=("", 16, "bold"), width=60)
        self.label_value.grid(row=0, column=2, rowspan=2, padx=(5, 10), pady=5)

    def update_values(self, raw: float, output: float):
        """
        Met à jour l'affichage.

        Args:
            raw: Valeur brute normalisée (0.0–1.0)
            output: Valeur après courbe (0.0–1.0)
        """
        self._raw_value = max(0.0, min(1.0, raw))
        self._output_value = max(0.0, min(1.0, output))

        self.bar_raw.set(self._raw_value)
        self.bar_output.set(self._output_value)
        self.label_value.configure(text=f"{self._output_value * 100:.0f}%")
