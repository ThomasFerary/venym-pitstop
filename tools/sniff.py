#!/usr/bin/env python3
"""
Venym Pedals — USB Sniffer

Script standalone pour :
1. Énumérer les périphériques HID et trouver le pédalier
2. Lire les données brutes en temps réel (axes des pédales)
3. Détecter les interfaces vendor-defined (config)
4. Logger les paquets dans un fichier pour analyse

Usage :
    python tools/sniff.py                  # Énumère les périphériques
    python tools/sniff.py --vid 0x1234 --pid 0x5678   # Lit les données brutes
    python tools/sniff.py --vid 0x1234 --pid 0x5678 --log capture.bin  # Avec log
"""

import argparse
import sys
import time
import struct
from datetime import datetime


def enumerate_devices():
    """Énumère tous les périphériques HID et affiche ceux qui pourraient être le pédalier."""
    try:
        import hid
    except ImportError:
        print("Erreur : 'hidapi' non installé. Exécute : pip install hidapi")
        sys.exit(1)

    print("=== Périphériques HID détectés ===\n")

    devices = hid.enumerate()
    if not devices:
        print("Aucun périphérique HID trouvé.")
        return

    # Regrouper par VID/PID
    seen = {}
    for dev in devices:
        key = (dev["vendor_id"], dev["product_id"])
        if key not in seen:
            seen[key] = []
        seen[key].append(dev)

    for (vid, pid), devs in sorted(seen.items()):
        product = devs[0].get("product_string") or "?"
        manufacturer = devs[0].get("manufacturer_string") or "?"
        print(f"  VID: 0x{vid:04x}  PID: 0x{pid:04x}  — {manufacturer} / {product}")
        for d in devs:
            usage_page = d.get("usage_page", 0)
            usage = d.get("usage", 0)
            interface = d.get("interface_number", -1)
            print(f"    Interface {interface:2d}  "
                  f"Usage Page: 0x{usage_page:04x}  Usage: 0x{usage:04x}  "
                  f"{'<-- VENDOR-DEFINED' if usage_page >= 0xFF00 else ''}")
        print()

    print("Astuce : les interfaces avec Usage Page >= 0xFF00 sont vendor-defined")
    print("         (probablement l'interface de configuration du pédalier).")


def read_descriptors(vid: int, pid: int):
    """Lit les descripteurs USB détaillés via pyusb."""
    try:
        import usb.core
        import usb.util
    except ImportError:
        print("Erreur : 'pyusb' non installé. Exécute : pip install pyusb")
        return

    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        print(f"Périphérique 0x{vid:04x}:0x{pid:04x} non trouvé via pyusb.")
        return

    print(f"=== Descripteurs USB — 0x{vid:04x}:0x{pid:04x} ===\n")
    print(dev)


def sniff_hid(vid: int, pid: int, log_path: str | None = None, duration: float = 0):
    """Lit les données HID brutes en temps réel."""
    try:
        import hid
    except ImportError:
        print("Erreur : 'hidapi' non installé.")
        sys.exit(1)

    # Lister toutes les interfaces pour ce VID/PID
    interfaces = [d for d in hid.enumerate() if d["vendor_id"] == vid and d["product_id"] == pid]
    if not interfaces:
        print(f"Périphérique 0x{vid:04x}:0x{pid:04x} non trouvé.")
        sys.exit(1)

    print(f"=== Interfaces disponibles pour 0x{vid:04x}:0x{pid:04x} ===")
    for i, d in enumerate(interfaces):
        up = d.get("usage_page", 0)
        u = d.get("usage", 0)
        iface = d.get("interface_number", -1)
        vendor = " <VENDOR-DEFINED>" if up >= 0xFF00 else ""
        print(f"  [{i}] Interface {iface}  Usage Page: 0x{up:04x}  Usage: 0x{u:04x}{vendor}")
    print()

    # Ouvrir chaque interface accessible
    opened: list[tuple[hid.device, dict]] = []
    for d in interfaces:
        h = hid.device()
        try:
            h.open_path(d["path"])
            h.set_nonblocking(1)
            opened.append((h, d))
            iface = d.get("interface_number", -1)
            print(f"  Ouvert : interface {iface} (Usage Page 0x{d.get('usage_page', 0):04x})")
        except OSError as e:
            iface = d.get("interface_number", -1)
            print(f"  Échec interface {iface} : {e}")

    if not opened:
        print("\nImpossible d'ouvrir le périphérique.")
        print("Vérifie qu'aucune autre app (Venym Pitstop, jeu) ne l'utilise.")
        sys.exit(1)

    product = interfaces[0].get("product_string") or "?"
    print(f"\nConnecté à : {product} (0x{vid:04x}:0x{pid:04x})")
    print(f"Lecture sur {len(opened)} interface(s)... (Ctrl+C pour arrêter)\n")

    log_file = None
    if log_path:
        log_file = open(log_path, "wb")
        print(f"Log activé : {log_path}")

    packet_count = 0
    start_time = time.time()

    try:
        while True:
            got_data = False
            for h, info in opened:
                try:
                    data = h.read(64)
                except OSError:
                    continue
                if not data:
                    continue

                got_data = True
                packet_count += 1
                elapsed = time.time() - start_time
                iface = info.get("interface_number", -1)
                up = info.get("usage_page", 0)
                tag = f"IF{iface}"

                # Affichage hex
                hex_str = " ".join(f"{b:02x}" for b in data)
                print(f"[{elapsed:8.3f}s] {tag} ({len(data):2d}B) {hex_str}")

                # Tentative d'interprétation des axes (interfaces joystick)
                if up < 0xFF00 and len(data) >= 7:
                    try:
                        vals = struct.unpack_from("<3H", bytes(data), 1)
                        pct = [v / 65535 * 100 for v in vals]
                        print(f"           Axes (uint16 LE @1): "
                              f"Acc={pct[0]:5.1f}%  Frein={pct[1]:5.1f}%  Emb={pct[2]:5.1f}%")
                    except struct.error:
                        pass

                # Log binaire
                if log_file:
                    log_file.write(struct.pack("<dBH", elapsed, iface & 0xFF, len(data)))
                    log_file.write(bytes(data))
                    log_file.flush()

            if not got_data:
                time.sleep(0.001)  # Éviter 100% CPU en non-blocking

            if duration > 0 and (time.time() - start_time) >= duration:
                break

    except KeyboardInterrupt:
        print(f"\n\nArrêté. {packet_count} paquets capturés en {time.time() - start_time:.1f}s.")

    finally:
        for h, _ in opened:
            h.close()
        if log_file:
            log_file.close()


def replay_log(log_path: str):
    """Rejoue un fichier de capture binaire."""
    with open(log_path, "rb") as f:
        packet_count = 0
        while True:
            header = f.read(10)  # float64 + uint16
            if len(header) < 10:
                break
            elapsed, length = struct.unpack("<dH", header)
            data = f.read(length)
            if len(data) < length:
                break
            packet_count += 1
            hex_str = " ".join(f"{b:02x}" for b in data)
            print(f"[{elapsed:8.3f}s] ({length:2d}B) {hex_str}")

    print(f"\n{packet_count} paquets dans le fichier.")


def main():
    parser = argparse.ArgumentParser(
        description="Venym Pedals — USB Sniffer & Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python tools/sniff.py                              # Lister les périphériques
  python tools/sniff.py --vid 0x1234 --pid 0x5678    # Sniffer en live
  python tools/sniff.py --vid 0x1234 --pid 0x5678 --log dump.bin
  python tools/sniff.py --replay dump.bin            # Rejouer une capture
  python tools/sniff.py --vid 0x1234 --pid 0x5678 --descriptors
        """,
    )
    parser.add_argument("--vid", type=lambda x: int(x, 0), help="Vendor ID (hex, ex: 0x1234)")
    parser.add_argument("--pid", type=lambda x: int(x, 0), help="Product ID (hex, ex: 0x5678)")
    parser.add_argument("--log", type=str, help="Fichier de log binaire")
    parser.add_argument("--replay", type=str, help="Rejouer un fichier de capture")
    parser.add_argument("--descriptors", action="store_true", help="Afficher les descripteurs USB (pyusb)")
    parser.add_argument("--duration", type=float, default=0, help="Durée de capture en secondes (0 = infini)")

    args = parser.parse_args()

    if args.replay:
        replay_log(args.replay)
        return

    if args.vid and args.pid:
        if args.descriptors:
            read_descriptors(args.vid, args.pid)
        else:
            sniff_hid(args.vid, args.pid, log_path=args.log, duration=args.duration)
    else:
        enumerate_devices()


if __name__ == "__main__":
    main()
