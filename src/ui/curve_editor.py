"""
Venym Pitstop — Curve Editor

Éditeur graphique de courbe de réponse avec interpolation cubique.
Les points de contrôle sont déplaçables à la souris.
"""

import tkinter as tk
import numpy as np

from ..core.config import ResponseCurve, CurvePoint


class CurveEditor(tk.Canvas):
    """
    Éditeur de courbe de réponse intégré dans un Canvas Tkinter.

    Fonctionnalités :
    - Affichage de la courbe interpolée cubique
    - Points de contrôle drag & drop
    - Double-clic pour ajouter un point
    - Clic droit pour supprimer un point
    - Prévisualisation de la valeur actuelle de la pédale
    """

    PADDING = 40
    POINT_RADIUS = 6
    GRID_COLOR = "#202530"
    CURVE_COLOR = "#00cc66"
    POINT_COLOR = "#D3E4FF"
    POINT_ACTIVE_COLOR = "#ff6600"
    PREVIEW_COLOR = "#ffcc00"
    BG_COLOR = "#0E131B"

    def __init__(self, master, curve: ResponseCurve | None = None,
                 on_change=None, **kwargs):
        kwargs.setdefault("bg", self.BG_COLOR)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)

        self.curve = curve or ResponseCurve()
        self._on_change = on_change
        self._dragging_index: int | None = None
        self._preview_x: float | None = None
        self._dz_low: float = 0.0   # Dead zone basse (0.0–1.0)
        self._dz_high: float = 0.0  # Dead zone haute (0.0–1.0)

        # Bindings
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Configure>", lambda e: self.redraw())

    @property
    def plot_width(self) -> int:
        return self.winfo_width() - 2 * self.PADDING

    @property
    def plot_height(self) -> int:
        return self.winfo_height() - 2 * self.PADDING

    def _to_canvas(self, x: float, y: float) -> tuple[float, float]:
        """Coordonnées normalisées (0–1) → coordonnées canvas."""
        cx = self.PADDING + x * self.plot_width
        cy = self.PADDING + (1.0 - y) * self.plot_height  # Y inversé
        return cx, cy

    def _to_normalized(self, cx: float, cy: float) -> tuple[float, float]:
        """Coordonnées canvas → normalisées (0–1)."""
        x = (cx - self.PADDING) / max(self.plot_width, 1)
        y = 1.0 - (cy - self.PADDING) / max(self.plot_height, 1)
        return np.clip(x, 0.0, 1.0), np.clip(y, 0.0, 1.0)

    def set_curve(self, curve: ResponseCurve):
        """Remplace la courbe et redessine."""
        self.curve = curve
        self.redraw()

    def set_preview(self, x: float | None):
        """Affiche un marqueur de prévisualisation à la position x."""
        self._preview_x = x
        self.redraw()

    def set_dead_zones(self, dz_low: float, dz_high: float):
        """Met à jour les dead zones (en fraction 0.0–1.0)."""
        self._dz_low = dz_low
        self._dz_high = dz_high
        self.redraw()

    def redraw(self):
        """Redessine l'intégralité du canvas."""
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        self._draw_grid()
        self._draw_curve()
        self._draw_preview()
        self._draw_points()

    def _draw_grid(self):
        """Dessine la grille de fond."""
        # Grille 10%
        for i in range(11):
            frac = i / 10.0
            x0, y0 = self._to_canvas(frac, 0)
            x1, y1 = self._to_canvas(frac, 1)
            self.create_line(x0, y0, x1, y1, fill=self.GRID_COLOR, dash=(2, 4))

            x0, y0 = self._to_canvas(0, frac)
            x1, y1 = self._to_canvas(1, frac)
            self.create_line(x0, y0, x1, y1, fill=self.GRID_COLOR, dash=(2, 4))

        # Diagonale (linéaire)
        x0, y0 = self._to_canvas(0, 0)
        x1, y1 = self._to_canvas(1, 1)
        self.create_line(x0, y0, x1, y1, fill="#444444", dash=(4, 4))


    def _draw_dead_zones(self):
        """Dessine les dead zones horizontales (sortie coupée en bas et en haut)."""
        # Dead zone basse : bande horizontale en bas (y=0 à y=dz_low)
        if self._dz_low > 0.001:
            # Ligne horizontale
            lx0, ly0 = self._to_canvas(0, self._dz_low)
            lx1, ly1 = self._to_canvas(1, self._dz_low)
            self.create_line(lx0, ly0, lx1, ly1, fill="#cc3333", dash=(4, 4), width=1)
            # Zone remplie
            bx0, by0 = self._to_canvas(0, 0)
            bx1, by1 = self._to_canvas(1, self._dz_low)
            self.create_rectangle(bx0, by0, bx1, by1, fill="#cc3333",
                                   stipple="gray25", outline="")

        # Dead zone haute : bande horizontale en haut (y=1-dz_high à y=1)
        if self._dz_high > 0.001:
            threshold = 1.0 - self._dz_high
            # Ligne horizontale
            lx0, ly0 = self._to_canvas(0, threshold)
            lx1, ly1 = self._to_canvas(1, threshold)
            self.create_line(lx0, ly0, lx1, ly1, fill="#cc3333", dash=(4, 4), width=1)
            # Zone remplie
            bx0, by0 = self._to_canvas(0, threshold)
            bx1, by1 = self._to_canvas(1, 1)
            self.create_rectangle(bx0, by0, bx1, by1, fill="#cc3333",
                                   stipple="gray25", outline="")

    def _draw_curve(self):
        """Dessine la courbe interpolée."""
        xs = np.linspace(0, 1, 200)
        ys = self.curve.evaluate_array(xs)

        coords = []
        for x, y in zip(xs, ys):
            cx, cy = self._to_canvas(float(x), float(y))
            coords.extend([cx, cy])

        if len(coords) >= 4:
            self.create_line(*coords, fill=self.CURVE_COLOR, width=2, smooth=False)

    def _draw_points(self):
        """Dessine les points de contrôle."""
        r = self.POINT_RADIUS
        for i, p in enumerate(self.curve.points):
            cx, cy = self._to_canvas(p.x, p.y)
            color = self.POINT_ACTIVE_COLOR if i == self._dragging_index else self.POINT_COLOR
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             fill=color, outline=self.CURVE_COLOR, width=2)

    def _draw_preview(self):
        """Dessine le marqueur de prévisualisation."""
        if self._preview_x is None:
            return
        x = self._preview_x
        y = self.curve.evaluate(x)
        cx, cy = self._to_canvas(x, y)

        # Lignes de guidage
        bx, by = self._to_canvas(x, 0)
        self.create_line(cx, cy, bx, by, fill=self.PREVIEW_COLOR, dash=(3, 3))
        lx, ly = self._to_canvas(0, y)
        self.create_line(cx, cy, lx, ly, fill=self.PREVIEW_COLOR, dash=(3, 3))

        # Point
        r = 4
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill=self.PREVIEW_COLOR, outline="")

    def _find_nearest_point(self, cx: float, cy: float) -> int | None:
        """Trouve le point de contrôle le plus proche du clic."""
        threshold = self.POINT_RADIUS * 3
        best_idx = None
        best_dist = float("inf")

        for i, p in enumerate(self.curve.points):
            px, py = self._to_canvas(p.x, p.y)
            dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if dist < threshold and dist < best_dist:
                best_dist = dist
                best_idx = i

        return best_idx

    def _on_click(self, event):
        self._dragging_index = self._find_nearest_point(event.x, event.y)
        self.redraw()

    def _on_drag(self, event):
        if self._dragging_index is None:
            return
        x, y = self._to_normalized(event.x, event.y)

        # Bloquer le x des points firmware (positions fixes 0, 0.2, 0.4, 0.6, 0.8, 1.0)
        # Seul le y est modifiable par drag
        current_x = self.curve.points[self._dragging_index].x
        self.curve.set_point(self._dragging_index, current_x, float(y))
        self.redraw()

    def _on_release(self, event):
        if self._dragging_index is not None:
            self._dragging_index = None
            self.redraw()
            if self._on_change:
                self._on_change(self.curve)

    def _on_double_click(self, event):
        """Double-clic : ajouter un point seulement si loin de tous les points existants."""
        if self._find_nearest_point(event.x, event.y) is not None:
            return  # Trop proche d'un point existant
        x, y = self._to_normalized(event.x, event.y)
        self.curve.add_point(float(x), float(y))
        self.redraw()
        if self._on_change:
            self._on_change(self.curve)

    def _on_right_click(self, event):
        """Clic droit : supprimer le point le plus proche."""
        idx = self._find_nearest_point(event.x, event.y)
        if idx is not None and idx != 0 and idx != len(self.curve.points) - 1:
            self.curve.remove_point(idx)
            self.redraw()
            if self._on_change:
                self._on_change(self.curve)
