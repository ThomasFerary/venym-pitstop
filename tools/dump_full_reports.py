#!/usr/bin/env python3
"""
Venym Pedals — Full Report Dump

Dumps the FULL 64 bytes of each Feature Report to discover
global settings, LED colors, and other unexplored data.

Known structure (38 bytes) is annotated. Bytes beyond 38 are
candidates for global settings (invert, LED flicker, LED intensity,
LED colors, ABS telemetry flag).

Usage:
    python tools/dump_full_reports.py
"""

import struct
import sys

VID, PID = 0x3441, 0x1501


def dump_report(h, report_id: int, name: str):
    """Read and display full 64 bytes of a Feature Report."""
    try:
        data = h.get_feature_report(report_id, 64)
    except OSError:
        print(f"  Report 0x{report_id:02x} ({name}): ERREUR lecture")
        return None

    if not data:
        print(f"  Report 0x{report_id:02x} ({name}): pas de données")
        return None

    raw = bytes(data)
    print(f"\n=== Report 0x{report_id:02x} — {name} ({len(raw)} bytes) ===")
    print(f"  Hex: {' '.join(f'{b:02x}' for b in raw)}")

    # Show as rows of 16
    for offset in range(0, len(raw), 16):
        chunk = raw[offset:offset + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        known = " <-- KNOWN" if offset < 38 and report_id >= 0x10 else ""
        print(f"  [{offset:3d}] {hex_part:<48s} {ascii_part}{known}")

    return raw


def annotate_pedal(raw: bytes, name: str):
    """Annotate the known 38-byte pedal structure."""
    if len(raw) < 38:
        return
    print(f"\n  --- Annotation {name} (38 bytes connus) ---")
    print(f"  [0]  version     = 0x{raw[0]:02x}")
    print(f"  [1]  mode_flag   = 0x{raw[1]:02x}")
    print(f"  [2]  pedal_type  = 0x{raw[2]:02x} ({'load cell' if raw[2] == 0x10 else 'hall'})")
    print(f"  [3]  enabled     = {raw[3]}")
    print(f"  [4]  nb_points   = {raw[4]}")
    print(f"  [5]  reserved    = 0x{raw[5]:02x}")
    print(f"  [6]  y1_implicit = {raw[6]}")
    print(f"  [7]  reserved    = 0x{raw[7]:02x}")

    print(f"  [8:23] Courbe (5 triplets):")
    for i in range(5):
        base = 8 + i * 3
        print(f"    point {i+1}: x={raw[base]}% y1={raw[base+1]} y2={raw[base+2]}")

    cal_min = struct.unpack_from("<H", raw, 23)[0]
    cal_max = struct.unpack_from("<H", raw, 25)[0]
    print(f"  [23:25] cal_min   = {cal_min}")
    print(f"  [25:27] cal_max   = {cal_max}")
    print(f"  [27]    reserved  = 0x{raw[27]:02x}")
    print(f"  [28:33] mapping   = {list(raw[28:33])}")
    print(f"  [33]    max_out   = {raw[33]}")
    pa = struct.unpack_from("<H", raw, 34)[0]
    pb = struct.unpack_from("<H", raw, 36)[0]
    print(f"  [34:36] param_a   = {pa} ({pa/100:.1f}%)")
    print(f"  [36:38] param_b   = {pb}")

    # UNEXPLORED BYTES
    if len(raw) > 38:
        unexplored = raw[38:]
        non_zero = [(38 + i, b) for i, b in enumerate(unexplored) if b != 0]
        print(f"\n  --- Bytes inexplores [{38}:{len(raw)}] ({len(unexplored)} bytes) ---")
        print(f"  Hex: {' '.join(f'{b:02x}' for b in unexplored)}")
        if non_zero:
            print(f"  NON-ZERO bytes:")
            for offset, val in non_zero:
                print(f"    [{offset}] = 0x{val:02x} ({val})")
        else:
            print(f"  Tous à zéro.")


def probe_unknown_reports(h):
    """Try reading report IDs not yet documented."""
    print("\n=== Probe de reports inconnus (0x00-0x20, skip connus) ===")
    known = {0x03, 0x05, 0x10, 0x11, 0x12}
    found = []
    for rid in range(0x00, 0x21):
        if rid in known:
            continue
        try:
            data = h.get_feature_report(rid, 64)
            if data and any(b != 0 for b in data):
                raw = bytes(data)
                hex_str = " ".join(f"{b:02x}" for b in raw[:32])
                print(f"  Report 0x{rid:02x}: [{len(raw)}B] {hex_str}...")
                found.append((rid, raw))
        except OSError:
            pass

    if not found:
        print("  Aucun report inconnu trouvé dans la plage 0x00-0x20.")

    # Also try 0x13-0x1F (near pedal reports)
    print("\n=== Probe reports 0x13-0x1F (proches des reports pédale) ===")
    for rid in range(0x13, 0x20):
        try:
            data = h.get_feature_report(rid, 64)
            if data and any(b != 0 for b in data):
                raw = bytes(data)
                hex_str = " ".join(f"{b:02x}" for b in raw[:32])
                print(f"  Report 0x{rid:02x}: [{len(raw)}B] {hex_str}...")
                found.append((rid, raw))
        except OSError:
            pass

    return found


def main():
    try:
        import hid
    except ImportError:
        print("Erreur : 'hidapi' non installé. pip install hidapi")
        sys.exit(1)

    h = hid.device()
    try:
        h.open(VID, PID)
    except OSError as e:
        print(f"Impossible d'ouvrir le pédalier : {e}")
        sys.exit(1)

    product = h.get_product_string() or "?"
    print(f"Connecté à : {product} (0x{VID:04x}:0x{PID:04x})")

    # Dump known reports
    r03 = dump_report(h, 0x03, "Firmware Info")
    r05 = dump_report(h, 0x05, "Global Cal / ADC")
    r10 = dump_report(h, 0x10, "Throttle Config")
    r11 = dump_report(h, 0x11, "Brake Config")
    r12 = dump_report(h, 0x12, "Clutch Config")

    # Annotate pedal reports
    if r10:
        annotate_pedal(r10, "Throttle")
    if r11:
        annotate_pedal(r11, "Brake")
    if r12:
        annotate_pedal(r12, "Clutch")

    # Probe unknown reports
    unknown = probe_unknown_reports(h)

    h.close()

    print("\n=== Résumé ===")
    print("Les bytes inexploités dans les reports 0x10-0x12 (au-delà de [38])")
    print("et les éventuels reports inconnus sont candidats pour :")
    print("  - Inversion pédales (swap left/right connectors)")
    print("  - Seuil flicker LEDs frein (%)")
    print("  - Intensité max LEDs (%)")
    print("  - Flag ABS telemetry flicker")
    print("  - Couleurs LEDs (RGB per pedal, 100% et 0%)")
    if unknown:
        print(f"\n  {len(unknown)} report(s) inconnu(s) trouvé(s) !")


if __name__ == "__main__":
    main()
