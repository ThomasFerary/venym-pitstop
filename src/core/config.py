"""
Venym Pedals — Configuration Model

Modèle de données pour la configuration du pédalier.
Sert de pont entre l'UI, les profils JSON, et le protocole USB.
"""

from dataclasses import dataclass, field
import numpy as np
from scipy.interpolate import CubicSpline


@dataclass
class CurvePoint:
    """Point de contrôle sur une courbe de réponse (0.0–1.0)."""
    x: float
    y: float

    def to_dict(self) -> dict:
        return {"x": round(self.x, 4), "y": round(self.y, 4)}

    @staticmethod
    def from_dict(d: dict) -> "CurvePoint":
        return CurvePoint(x=float(d["x"]), y=float(d["y"]))


class ResponseCurve:
    """
    Courbe de réponse d'une pédale avec interpolation cubique.

    Les points de contrôle définissent la forme de la courbe.
    L'interpolation cubique (comme l'originale Venym) génère une courbe lisse.
    """

    def __init__(self, points: list[CurvePoint] | None = None):
        self.points = points or self._default_points()
        self._spline: CubicSpline | None = None
        self._rebuild_spline()

    @staticmethod
    def _default_points() -> list[CurvePoint]:
        """Courbe linéaire par défaut (6 points aux positions firmware)."""
        return [
            CurvePoint(0.0, 0.0),
            CurvePoint(0.2, 0.2),
            CurvePoint(0.4, 0.4),
            CurvePoint(0.6, 0.6),
            CurvePoint(0.8, 0.8),
            CurvePoint(1.0, 1.0),
        ]

    def _rebuild_spline(self):
        """Reconstruit la spline cubique à partir des points de contrôle."""
        if len(self.points) < 2:
            self._spline = None
            return
        # Trier par x
        self.points.sort(key=lambda p: p.x)
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        self._spline = CubicSpline(xs, ys, bc_type="natural")

    def evaluate(self, x: float) -> float:
        """Évalue la courbe à une position donnée (0.0–1.0)."""
        if self._spline is None:
            return x  # Linéaire par défaut
        result = float(self._spline(np.clip(x, 0.0, 1.0)))
        return float(np.clip(result, 0.0, 1.0))

    def evaluate_array(self, xs: np.ndarray) -> np.ndarray:
        """Évalue la courbe sur un tableau de valeurs (pour l'affichage)."""
        if self._spline is None:
            return xs
        return np.clip(self._spline(np.clip(xs, 0.0, 1.0)), 0.0, 1.0)

    def set_point(self, index: int, x: float, y: float):
        """Modifie un point de contrôle et reconstruit la spline."""
        if 0 <= index < len(self.points):
            self.points[index] = CurvePoint(
                x=np.clip(x, 0.0, 1.0),
                y=np.clip(y, 0.0, 1.0),
            )
            self._rebuild_spline()

    def add_point(self, x: float, y: float):
        """Ajoute un point de contrôle."""
        self.points.append(CurvePoint(x=np.clip(x, 0.0, 1.0), y=np.clip(y, 0.0, 1.0)))
        self._rebuild_spline()

    def remove_point(self, index: int):
        """Supprime un point (minimum 2 points)."""
        if len(self.points) > 2 and 0 <= index < len(self.points):
            self.points.pop(index)
            self._rebuild_spline()

    def to_dict(self) -> list[dict]:
        return [p.to_dict() for p in self.points]

    @staticmethod
    def from_dict(data: list[dict]) -> "ResponseCurve":
        points = [CurvePoint.from_dict(d) for d in data]
        return ResponseCurve(points)


@dataclass
class PedalConfig:
    """Configuration complète d'une pédale."""
    name: str
    dead_zone_low: float = 0.0    # Dead zone basse en % (pas utilisé directement, voir fw_param_a)
    dead_zone_high: float = 0.0   # Dead zone haute en % (0 = pas de DZ, 2 = 2%)
    cal_min: int = 0              # ADC min (relâché) — à calibrer
    cal_max: int = 65535          # ADC max — à calibrer
    curve: ResponseCurve = field(default_factory=ResponseCurve)
    # Valeurs firmware brutes (Feature Report)
    fw_param_a: int = 0           # [34:36] — dead zone / offset
    fw_param_b: int = 0           # [36:38] — force frein
    fw_curve_y1: list[int] = field(default_factory=lambda: [77, 81, 83, 85, 86])  # y1 firmware
    fw_curve_y2: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])  # y2 tangent bytes

    def apply(self, raw_value: int) -> float:
        """
        Applique la chaîne complète : calibration → dead zones → courbe.

        Args:
            raw_value: Valeur brute ADC (0–0xFFFFF)

        Returns:
            Valeur finale normalisée (0.0–1.0)
        """
        # 1. Calibration : normaliser en 0.0–1.0
        cal_range = self.cal_max - self.cal_min
        if cal_range <= 0:
            return 0.0
        normalized = (raw_value - self.cal_min) / cal_range
        normalized = max(0.0, min(1.0, normalized))

        # 2. Dead zones
        dz_range = self.dead_zone_high - self.dead_zone_low
        if dz_range <= 0:
            return 0.0
        if normalized <= self.dead_zone_low:
            return 0.0
        if normalized >= self.dead_zone_high:
            return 1.0
        adjusted = (normalized - self.dead_zone_low) / dz_range

        # 3. Courbe de réponse
        return self.curve.evaluate(adjusted)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "dead_zone_low": round(self.dead_zone_low, 4),
            "dead_zone_high": round(self.dead_zone_high, 4),
            "cal_min": self.cal_min,
            "cal_max": self.cal_max,
            "curve": self.curve.to_dict(),
            "fw_param_a": self.fw_param_a,
            "fw_param_b": self.fw_param_b,
        }

    @staticmethod
    def from_dict(data: dict) -> "PedalConfig":
        return PedalConfig(
            name=data["name"],
            dead_zone_low=data.get("dead_zone_low", 0.0),
            dead_zone_high=data.get("dead_zone_high", 1.0),
            cal_min=data.get("cal_min", 0),
            cal_max=data.get("cal_max", 65535),
            curve=ResponseCurve.from_dict(data.get("curve", [])) if data.get("curve") else ResponseCurve(),
            fw_param_a=data.get("fw_param_a", 0),
            fw_param_b=data.get("fw_param_b", 0),
        )


@dataclass
class FullConfig:
    """Configuration complète du pédalier (3 pédales)."""
    throttle: PedalConfig
    brake: PedalConfig
    clutch: PedalConfig

    @staticmethod
    def default() -> "FullConfig":
        return FullConfig(
            throttle=PedalConfig(name="Accélérateur"),
            brake=PedalConfig(name="Frein"),
            clutch=PedalConfig(name="Embrayage"),
        )

    def to_dict(self) -> dict:
        return {
            "throttle": self.throttle.to_dict(),
            "brake": self.brake.to_dict(),
            "clutch": self.clutch.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict) -> "FullConfig":
        return FullConfig(
            throttle=PedalConfig.from_dict(data["throttle"]),
            brake=PedalConfig.from_dict(data["brake"]),
            clutch=PedalConfig.from_dict(data["clutch"]),
        )
