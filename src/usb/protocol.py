"""
Venym Pedals — USB Protocol

Encodage et décodage de la configuration du pédalier via HID Feature Reports.

Feature Reports identifiés :
    0x03 — Info firmware (9B, lecture seule)
    0x05 — Calibration globale? (6B)
    0x10 — Config accélérateur (38B)
    0x11 — Config frein (38B)
    0x12 — Config embrayage (38B)
"""

import struct
from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np
from scipy.interpolate import interp1d

# === Firmware curve LUT ===
# Courbe linéaire de référence (mesurée : ces y1 produisent une sortie linéaire)
# La correspondance est PAR POINT, pas globale.
_LINEAR_Y1 = [0, 77, 81, 83, 85, 86]     # y1 firmware pour 0%, 20%, 40%, 60%, 80%, 100%
_LINEAR_OUT = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]  # sortie réelle correspondante

# y1 → output (pour décoder la courbe lue du pédalier)
_fw_y1_to_output = interp1d(_LINEAR_Y1, _LINEAR_OUT, kind='linear',
                             fill_value=(0.0, 1.0), bounds_error=False)

# output → y1 (pour encoder la courbe à envoyer au pédalier)
_fw_output_to_y1 = interp1d(_LINEAR_OUT, _LINEAR_Y1, kind='linear',
                              fill_value=(0, 86), bounds_error=False)


def fw_y1_to_output_pct(y1: int) -> float:
    """Convertit y1 firmware en output normalisé (0.0–1.0)."""
    return float(np.clip(_fw_y1_to_output(y1), 0.0, 1.0))


def output_pct_to_fw_y1(output: float) -> int:
    """Convertit output normalisé (0.0–1.0) en y1 firmware."""
    y1 = float(_fw_output_to_y1(np.clip(output, 0.0, 1.0)))
    y1 = int(round(y1))
    if y1 == 127:
        y1 = 126
    return max(0, min(86, y1))


class FeatureReport(IntEnum):
    """Report IDs des Feature Reports."""
    FIRMWARE_INFO = 0x03
    GLOBAL_CAL = 0x05
    PEDAL_THROTTLE = 0x10
    PEDAL_BRAKE = 0x11
    PEDAL_CLUTCH = 0x12


class Pedal(IntEnum):
    THROTTLE = 0
    BRAKE = 1
    CLUTCH = 2


# Mapping report_id <-> pedal
REPORT_TO_PEDAL = {
    FeatureReport.PEDAL_THROTTLE: Pedal.THROTTLE,
    FeatureReport.PEDAL_BRAKE: Pedal.BRAKE,
    FeatureReport.PEDAL_CLUTCH: Pedal.CLUTCH,
}
PEDAL_TO_REPORT = {v: k for k, v in REPORT_TO_PEDAL.items()}


@dataclass
class CurvePoint:
    """Point de courbe tel que stocké sur le pédalier."""
    x_pct: int    # Input en % (0–100)
    y_byte1: int  # Encodage output (byte 1) — signification exacte TBD
    y_byte2: int  # Encodage output (byte 2) — signification exacte TBD


@dataclass
class FirmwareInfo:
    """Report 0x03 — Info firmware."""
    num_pedals: int
    serial: bytes  # 3 bytes
    build: int     # uint16 LE

    @staticmethod
    def from_report(data: bytes | list[int]) -> "FirmwareInfo":
        if isinstance(data, list):
            data = bytes(data)
        return FirmwareInfo(
            num_pedals=data[0],
            serial=data[1:4],
            build=struct.unpack_from("<H", data, 7)[0],
        )


@dataclass
class PedalReport:
    """
    Report 0x10/0x11/0x12 — Configuration d'une pédale (38B).

    Structure :
        [0]     version (0x04)
        [1]     reserved
        [2]     pedal_flags (0x00=accel/emb, 0x10=frein)
        [3]     enabled (0x01)
        [4]     param_06 (=6, nb points+1?)
        [5:8]   reserved
        [8:23]  curve (5 triplets de 3 bytes)
        [23:25] cal_min (uint16 LE)
        [25:27] cal_max (uint16 LE)
        [27]    reserved
        [28:33] physical_mapping (5 bytes, 0xFF marks position)
        [33]    max_output_pct (=100)
        [34:36] param_a (uint16 LE)
        [36:38] param_b (uint16 LE)
    """
    version: int = 0x04
    pedal_flags: int = 0x00
    enabled: int = 0x01
    param_06: int = 0x06

    curve_points: list[CurvePoint] = field(default_factory=list)

    cal_min: int = 0
    cal_max: int = 65535
    physical_mapping: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    max_output_pct: int = 100
    param_a: int = 0
    param_b: int = 0

    @staticmethod
    def from_report(data: bytes | list[int]) -> "PedalReport":
        """Parse un Feature Report brut (38B) en PedalReport."""
        if isinstance(data, list):
            data = bytes(data)
        if len(data) < 38:
            raise ValueError(f"Report trop court : {len(data)} bytes (attendu 38)")

        # Curve: 5 triplets de 3 bytes à partir de l'offset 8
        curve = []
        for i in range(5):
            base = 8 + i * 3
            curve.append(CurvePoint(
                x_pct=data[base],
                y_byte1=data[base + 1],
                y_byte2=data[base + 2],
            ))

        return PedalReport(
            version=data[0],
            pedal_flags=data[2],
            enabled=data[3],
            param_06=data[4],
            curve_points=curve,
            cal_min=struct.unpack_from("<H", data, 23)[0],
            cal_max=struct.unpack_from("<H", data, 25)[0],
            physical_mapping=list(data[28:33]),
            max_output_pct=data[33],
            param_a=struct.unpack_from("<H", data, 34)[0],
            param_b=struct.unpack_from("<H", data, 36)[0],
        )

    def to_bytes(self) -> bytes:
        """Encode en 38 bytes pour Set Feature Report."""
        buf = bytearray(38)

        buf[0] = self.version
        buf[1] = 0x00
        buf[2] = self.pedal_flags
        buf[3] = self.enabled
        buf[4] = self.param_06
        # [5:8] reserved

        # Curve: 5 triplets
        for i, pt in enumerate(self.curve_points[:5]):
            base = 8 + i * 3
            buf[base] = pt.x_pct & 0xFF
            buf[base + 1] = pt.y_byte1 & 0xFF
            buf[base + 2] = pt.y_byte2 & 0xFF

        struct.pack_into("<H", buf, 23, self.cal_min & 0xFFFF)
        struct.pack_into("<H", buf, 25, self.cal_max & 0xFFFF)
        buf[27] = 0x00

        for i, v in enumerate(self.physical_mapping[:5]):
            buf[28 + i] = v & 0xFF

        buf[33] = self.max_output_pct & 0xFF
        struct.pack_into("<H", buf, 34, self.param_a & 0xFFFF)
        struct.pack_into("<H", buf, 36, self.param_b & 0xFFFF)

        return bytes(buf)


def read_pedal_config(device, pedal: Pedal) -> PedalReport:
    """Lit la config d'une pédale via Get Feature Report."""
    report_id = PEDAL_TO_REPORT[pedal]
    data = device.get_feature_report(report_id, 64)
    return PedalReport.from_report(data)


def write_pedal_config(device, pedal: Pedal, config: PedalReport) -> bool:
    """
    Écrit la config d'une pédale via Set Feature Report.

    Format confirmé :
        payload[0]    = report_id (transport HID)
        payload[1]    = report_id (sélecteur pédale)
        payload[2:40] = données config (38 bytes)
        payload[40:64] = padding 0x00
        Total = 64 bytes
    """
    report_id = PEDAL_TO_REPORT[pedal]
    config_bytes = config.to_bytes()  # 38 bytes

    # Construire le payload de 63 bytes (sans le transport byte)
    payload_inner = bytearray(63)
    payload_inner[0] = report_id  # Sélecteur pédale
    payload_inner[1:1 + len(config_bytes)] = config_bytes

    # send_feature_report attend : [transport_id] + [63B payload]
    full_payload = bytes([report_id]) + bytes(payload_inner)

    try:
        device.send_feature_report(full_payload)
        return True
    except OSError:
        return False


def read_firmware_info(device) -> FirmwareInfo:
    """Lit les infos firmware via Get Feature Report 0x03."""
    data = device.get_feature_report(FeatureReport.FIRMWARE_INFO, 64)
    return FirmwareInfo.from_report(data)


def parse_input_report(data: bytes | list[int]) -> dict:
    """
    Parse un Input Report (7B) des axes.

    Retourne : {"report_id": int, "throttle": int, "brake": int,
                "model_byte1": int, "model_byte2": int}
    """
    if isinstance(data, list):
        data = bytes(data)
    if len(data) < 5:
        raise ValueError(f"Input report trop court : {len(data)} bytes")

    throttle, brake = struct.unpack_from("<HH", data, 1)
    result = {
        "report_id": data[0],
        "throttle": throttle,
        "brake": brake,
    }
    if len(data) >= 7:
        result["model_byte1"] = data[5]
        result["model_byte2"] = data[6]
    return result
