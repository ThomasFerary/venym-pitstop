#!/usr/bin/env python3
"""
Venym Pedals — Report 0x05 Deep Probe

Le report 0x05 retourne 7 bytes dont le 7ème (0x6c = 108) est inexpliqué.
Ce script explore si le report 0x05 contient des global settings
(LED, inversion, flicker) en testant l'écriture de différentes valeurs.

ATTENTION: Ce script modifie temporairement le report 0x05.
Les bytes 0-3 sont les ADC temps réel (écrasés immédiatement par le firmware).
Les bytes 4-6 pourraient être persistants.

Usage:
    python tools/probe_r05.py             # Lecture seule (safe)
    python tools/probe_r05.py --write     # Teste l'écriture (modifie le pédalier!)
    python tools/probe_r05.py --monitor   # Surveille les changements en continu
"""

import argparse
import struct
import sys
import time

VID, PID = 0x3441, 0x1501


def read_r05(h):
    """Lit le report 0x05 et affiche le détail."""
    data = h.get_feature_report(0x05, 64)
    if not data:
        print("Impossible de lire le report 0x05")
        return None
    raw = bytes(data)
    print(f"Report 0x05 ({len(raw)} bytes): {' '.join(f'{b:02x}' for b in raw)}")

    if len(raw) >= 4:
        adc_accel = struct.unpack_from("<H", raw, 0)[0]
        adc_brake = struct.unpack_from("<H", raw, 2)[0]
        print(f"  [0:2] ADC Accel  = {adc_accel}")
        print(f"  [2:4] ADC Brake  = {adc_brake}")
    if len(raw) >= 6:
        adc_clutch = struct.unpack_from("<H", raw, 4)[0]
        print(f"  [4:6] ADC Clutch = {adc_clutch}")
    if len(raw) >= 7:
        print(f"  [6]   Byte 7     = 0x{raw[6]:02x} ({raw[6]})")
        # Décomposer en bits
        b = raw[6]
        print(f"         Bits: {b:08b}")
        print(f"         Bit 0 (invert?):      {b & 1}")
        print(f"         Bit 1 (flicker en?):   {(b >> 1) & 1}")
        print(f"         Bit 2 (ABS flicker?):  {(b >> 2) & 1}")
        print(f"         Bits 3-7 (intensity?): {(b >> 3) & 0x1F} ({(b >> 3) & 0x1F}/31 = {((b >> 3) & 0x1F) / 31 * 100:.0f}%)")
        # Alternative: nibble split
        print(f"         High nibble: 0x{(b >> 4):x} ({b >> 4})")
        print(f"         Low nibble:  0x{(b & 0xF):x} ({b & 0xF})")
    return raw


def monitor_r05(h, duration=10):
    """Surveille le report 0x05 et affiche les changements."""
    print(f"\nSurveillance du report 0x05 pendant {duration}s...")
    print("Appuie sur les pédales et observe les changements.\n")

    last = None
    t0 = time.time()
    while time.time() - t0 < duration:
        data = h.get_feature_report(0x05, 64)
        if data:
            raw = bytes(data)
            if raw != last:
                elapsed = time.time() - t0
                hex_str = " ".join(f"{b:02x}" for b in raw)
                # Highlight differences
                if last:
                    diffs = []
                    for i in range(min(len(raw), len(last))):
                        if raw[i] != last[i]:
                            diffs.append(f"[{i}]: 0x{last[i]:02x}->0x{raw[i]:02x}")
                    print(f"[{elapsed:6.2f}s] {hex_str}  CHANGED: {', '.join(diffs)}")
                else:
                    print(f"[{elapsed:6.2f}s] {hex_str}")
                last = raw
        time.sleep(0.05)
    print("Fin monitoring.")


def test_write_r05(h):
    """Teste l'écriture sur le report 0x05."""
    print("\n=== Test écriture report 0x05 ===")
    print("ATTENTION: ceci modifie temporairement le pédalier.\n")

    # Lire l'état actuel
    orig = bytes(h.get_feature_report(0x05, 64))
    print(f"État initial: {' '.join(f'{b:02x}' for b in orig)}")

    if len(orig) < 7:
        print("Report trop court, abandon.")
        return

    orig_byte6 = orig[6]
    print(f"Byte 6 original: 0x{orig_byte6:02x} ({orig_byte6})\n")

    # Test 1: écrire 0x00 dans byte 6
    # Test 2: écrire 0xFF dans byte 6
    # Test 3: restaurer la valeur originale
    for test_val, desc in [(0x00, "all zeros"), (0xFF, "all ones"),
                            (0x6D, "original+1"), (orig_byte6, "restore original")]:
        payload = bytearray(64)
        payload[0] = 0x05  # Report ID (transport)
        # Le payload interne commence à [1]
        # On copie les bytes originaux et on modifie byte 6
        for i, b in enumerate(orig[:min(len(orig), 63)]):
            payload[1 + i] = b
        payload[1 + 6] = test_val

        print(f"Écriture byte 6 = 0x{test_val:02x} ({desc})...")
        try:
            h.send_feature_report(bytes(payload))
        except OSError as e:
            print(f"  Erreur écriture: {e}")
            continue

        time.sleep(0.3)

        # Relire
        check = h.get_feature_report(0x05, 64)
        if check:
            check_raw = bytes(check)
            print(f"  Relecture: {' '.join(f'{b:02x}' for b in check_raw)}")
            if len(check_raw) > 6:
                if check_raw[6] == test_val:
                    print(f"  ✓ Byte 6 = 0x{check_raw[6]:02x} (PERSISTANT!)")
                else:
                    print(f"  ✗ Byte 6 = 0x{check_raw[6]:02x} (écrasé par firmware)")
        print()

    # Lire aussi les bytes 4-5 (clutch ADC ou autre?)
    print("=== Analyse bytes 4-5 (embrayage/réservé) ===")
    for test_val in [0x0000, 0xFFFF]:
        payload = bytearray(64)
        payload[0] = 0x05
        for i, b in enumerate(orig[:min(len(orig), 63)]):
            payload[1 + i] = b
        struct.pack_into("<H", payload, 1 + 4, test_val)

        print(f"Écriture bytes 4-5 = 0x{test_val:04x}...")
        try:
            h.send_feature_report(bytes(payload))
        except OSError as e:
            print(f"  Erreur: {e}")
            continue

        time.sleep(0.3)
        check = h.get_feature_report(0x05, 64)
        if check:
            check_raw = bytes(check)
            check_val = struct.unpack_from("<H", check_raw, 4)[0]
            print(f"  Relecture bytes 4-5 = 0x{check_val:04x} ({'PERSISTANT' if check_val == test_val else 'écrasé'})")
        print()


def main():
    parser = argparse.ArgumentParser(description="Venym — Report 0x05 Deep Probe")
    parser.add_argument("--write", action="store_true", help="Teste l'écriture (modifie le pédalier!)")
    parser.add_argument("--monitor", action="store_true", help="Surveille les changements en continu")
    parser.add_argument("--duration", type=float, default=10, help="Durée monitoring (secondes)")
    args = parser.parse_args()

    try:
        import hid
    except ImportError:
        print("Erreur : pip install hidapi")
        sys.exit(1)

    h = hid.device()
    try:
        h.open(VID, PID)
    except OSError as e:
        print(f"Impossible d'ouvrir le pédalier : {e}")
        sys.exit(1)

    print(f"Connecté à : {h.get_product_string()} (0x{VID:04x}:0x{PID:04x})\n")

    read_r05(h)

    if args.monitor:
        monitor_r05(h, args.duration)

    if args.write:
        test_write_r05(h)

    h.close()


if __name__ == "__main__":
    main()
