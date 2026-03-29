"""
Venym Pedals — Capture & Analysis Tool

Outil de capture structurée des paquets USB pour faciliter le reverse engineering.
Capture les échanges, détecte les patterns, et génère des rapports.
"""

import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

from .device import VenymDevice


@dataclass
class CapturedPacket:
    """Un paquet capturé avec métadonnées."""
    timestamp: float
    direction: str  # "IN" (device → PC) ou "OUT" (PC → device)
    interface: str  # "axes" ou "config"
    data: bytes
    note: str = ""

    @property
    def hex_dump(self) -> str:
        return " ".join(f"{b:02x}" for b in self.data)

    @property
    def length(self) -> int:
        return len(self.data)


class CaptureSession:
    """
    Session de capture USB.

    Capture les paquets entrants et permet l'analyse de patterns.
    """

    def __init__(self):
        self.packets: list[CapturedPacket] = []
        self._start_time: float = 0

    def start(self):
        self._start_time = time.time()
        self.packets.clear()

    def record(self, data: bytes | list[int], direction: str = "IN",
               interface: str = "axes", note: str = ""):
        if isinstance(data, list):
            data = bytes(data)
        pkt = CapturedPacket(
            timestamp=time.time() - self._start_time,
            direction=direction,
            interface=interface,
            data=data,
            note=note,
        )
        self.packets.append(pkt)
        return pkt

    def save_binary(self, path: str | Path):
        """Sauvegarde la capture en format binaire."""
        path = Path(path)
        with path.open("wb") as f:
            # Header : magic + nombre de paquets
            f.write(b"VNYM")
            f.write(struct.pack("<I", len(self.packets)))

            for pkt in self.packets:
                # direction (1B) + interface (1B) + timestamp (f64) + data_len (u16) + data
                dir_byte = 0x00 if pkt.direction == "IN" else 0x01
                iface_byte = 0x00 if pkt.interface == "axes" else 0x01
                f.write(struct.pack("<BBdH", dir_byte, iface_byte,
                                    pkt.timestamp, len(pkt.data)))
                f.write(pkt.data)

    def load_binary(self, path: str | Path):
        """Charge une capture depuis un fichier binaire."""
        path = Path(path)
        self.packets.clear()

        with path.open("rb") as f:
            magic = f.read(4)
            if magic != b"VNYM":
                raise ValueError(f"Format invalide (magic: {magic!r})")

            count = struct.unpack("<I", f.read(4))[0]

            for _ in range(count):
                header = f.read(12)  # 1+1+8+2
                dir_byte, iface_byte, timestamp, data_len = struct.unpack("<BBdH", header)
                data = f.read(data_len)

                self.packets.append(CapturedPacket(
                    timestamp=timestamp,
                    direction="IN" if dir_byte == 0x00 else "OUT",
                    interface="axes" if iface_byte == 0x00 else "config",
                    data=data,
                ))

    def save_text(self, path: str | Path):
        """Exporte la capture en format texte lisible."""
        path = Path(path)
        with path.open("w") as f:
            f.write(f"Venym USB Capture — {len(self.packets)} packets\n")
            f.write("=" * 80 + "\n\n")

            for i, pkt in enumerate(self.packets):
                f.write(f"#{i:04d} [{pkt.timestamp:8.3f}s] {pkt.direction:3s} "
                        f"{pkt.interface:6s} ({pkt.length:2d}B) {pkt.hex_dump}\n")
                if pkt.note:
                    f.write(f"      Note: {pkt.note}\n")

    def find_patterns(self) -> dict:
        """
        Analyse basique des patterns dans les paquets capturés.

        Cherche :
        - Les bytes constants (même valeur dans tous les paquets)
        - Les bytes qui varient (probablement des données)
        - Les tailles de paquets récurrentes
        """
        if not self.packets:
            return {"error": "Aucun paquet capturé"}

        # Séparer par interface
        by_interface: dict[str, list[CapturedPacket]] = {}
        for pkt in self.packets:
            by_interface.setdefault(pkt.interface, []).append(pkt)

        result = {}
        for iface, pkts in by_interface.items():
            # Tailles de paquets
            sizes = [p.length for p in pkts]
            unique_sizes = sorted(set(sizes))

            # Bytes constants vs variables (sur les paquets de même taille)
            constant_bytes = {}
            for size in unique_sizes:
                same_size = [p.data for p in pkts if p.length == size]
                if len(same_size) < 2:
                    continue
                constants = {}
                for pos in range(size):
                    vals = {d[pos] for d in same_size}
                    if len(vals) == 1:
                        constants[pos] = next(iter(vals))
                if constants:
                    constant_bytes[size] = constants

            result[iface] = {
                "packet_count": len(pkts),
                "sizes": unique_sizes,
                "size_counts": {s: sizes.count(s) for s in unique_sizes},
                "constant_bytes": constant_bytes,
            }

        return result

    def diff_packets(self, idx_a: int, idx_b: int) -> str:
        """Compare deux paquets et affiche les différences."""
        if idx_a >= len(self.packets) or idx_b >= len(self.packets):
            return "Index invalide"

        a = self.packets[idx_a].data
        b = self.packets[idx_b].data
        max_len = max(len(a), len(b))

        lines = [f"Diff #{idx_a} vs #{idx_b}:", ""]
        for i in range(max_len):
            va = a[i] if i < len(a) else None
            vb = b[i] if i < len(b) else None
            if va != vb:
                sa = f"0x{va:02x}" if va is not None else "---"
                sb = f"0x{vb:02x}" if vb is not None else "---"
                lines.append(f"  Offset 0x{i:02x}: {sa} → {sb}")

        if len(lines) == 2:
            lines.append("  (paquets identiques)")

        return "\n".join(lines)
