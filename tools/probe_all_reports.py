#!/usr/bin/env python3
"""
Venym Pedals — Exhaustive Report Probe

Scans ALL report IDs 0x00-0xFF to find hidden Feature Reports
that may contain global settings (invert, LED flicker, LED colors, etc.)

Usage:
    python tools/probe_all_reports.py
"""

import sys
import time

VID, PID = 0x3441, 0x1501


def main():
    try:
        import hid
    except ImportError:
        print("pip install hidapi")
        sys.exit(1)

    h = hid.device()
    try:
        h.open(VID, PID)
    except OSError as e:
        print(f"Impossible d'ouvrir : {e}")
        sys.exit(1)

    print(f"Connecté à : {h.get_product_string()}\n")
    print("=== Probe exhaustif 0x00-0xFF ===\n")

    found = []
    known = {0x03: "Firmware Info", 0x05: "ADC Real-time",
             0x10: "Throttle", 0x11: "Brake", 0x12: "Clutch"}

    for rid in range(0x00, 0x100):
        for size in [8, 16, 32, 64]:
            try:
                data = h.get_feature_report(rid, size)
                if data:
                    raw = bytes(data)
                    tag = f" <-- {known[rid]}" if rid in known else " <-- NOUVEAU!"
                    hex_str = " ".join(f"{b:02x}" for b in raw)
                    print(f"  Report 0x{rid:02x} ({len(raw):2d}B): {hex_str}{tag}")
                    found.append((rid, raw))
                    break
            except OSError:
                break
            except Exception:
                break

    h.close()

    print(f"\n=== {len(found)} report(s) trouvé(s) ===")
    new_reports = [(rid, raw) for rid, raw in found if rid not in known]
    if new_reports:
        print(f"\n*** {len(new_reports)} NOUVEAU(X) REPORT(S) ! ***")
        for rid, raw in new_reports:
            print(f"  0x{rid:02x}: {len(raw)}B — {' '.join(f'{b:02x}' for b in raw)}")
    else:
        print("Aucun nouveau report trouvé.")


if __name__ == "__main__":
    main()
