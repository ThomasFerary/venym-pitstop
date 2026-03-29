#!/usr/bin/env python3
"""
Venym Pedals — Config Backup & Restore

Sauvegarde et restaure la configuration complète du pédalier.
INDISPENSABLE avant de tester l'écriture de Feature Reports.

Usage :
    python tools/backup.py --save backup.json      # Sauvegarder
    python tools/backup.py --restore backup.json    # Restaurer
    python tools/backup.py --dump                   # Afficher sans sauver
"""

import argparse
import json
import sys
import time

VID = 0x3441
PID = 0x1501

REPORT_IDS = {
    0x03: {"name": "firmware_info", "size": 64},
    0x05: {"name": "global_cal", "size": 64},
    0x10: {"name": "pedal_throttle", "size": 64},
    0x11: {"name": "pedal_brake", "size": 64},
    0x12: {"name": "pedal_clutch", "size": 64},
}


def open_device(vid: int, pid: int):
    import hid
    h = hid.device()
    try:
        h.open(vid, pid)
    except OSError as e:
        print(f"Impossible d'ouvrir 0x{vid:04x}:0x{pid:04x} : {e}")
        print("Ferme l'UI et les autres apps d'abord.")
        sys.exit(1)
    return h


def read_all_reports(h) -> dict:
    """Lit tous les Feature Reports connus."""
    reports = {}
    for report_id, info in REPORT_IDS.items():
        try:
            data = h.get_feature_report(report_id, info["size"])
            if data:
                reports[f"0x{report_id:02x}"] = {
                    "name": info["name"],
                    "size": len(data),
                    "hex": " ".join(f"{b:02x}" for b in data),
                    "raw": list(data),
                }
                print(f"  Report 0x{report_id:02x} ({info['name']}): {len(data)}B OK")
            else:
                print(f"  Report 0x{report_id:02x} ({info['name']}): vide")
        except OSError as e:
            print(f"  Report 0x{report_id:02x} ({info['name']}): erreur ({e})")
    return reports


def save_backup(path: str, vid: int, pid: int):
    """Sauvegarde tous les Feature Reports dans un fichier JSON."""
    h = open_device(vid, pid)
    print("Lecture des Feature Reports...")
    reports = read_all_reports(h)
    h.close()

    backup = {
        "vid": f"0x{vid:04x}",
        "pid": f"0x{pid:04x}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reports": reports,
    }

    with open(path, "w") as f:
        json.dump(backup, f, indent=2)

    print(f"\nBackup sauvegardé : {path} ({len(reports)} reports)")


def restore_backup(path: str, vid: int, pid: int):
    """Restaure les Feature Reports depuis un backup JSON."""
    with open(path) as f:
        backup = json.load(f)

    print(f"Backup chargé : {backup['timestamp']}")
    print(f"  VID/PID: {backup['vid']}:{backup['pid']}")
    print()

    h = open_device(vid, pid)

    # Ne restaurer que les reports de config pédale (pas firmware info)
    restore_ids = [0x10, 0x11, 0x12]

    for report_id in restore_ids:
        key = f"0x{report_id:02x}"
        if key not in backup["reports"]:
            print(f"  Report {key}: absent du backup, skip")
            continue

        raw = bytes(backup["reports"][key]["raw"])
        name = backup["reports"][key]["name"]

        # Préparer le payload : report_id + data
        payload = bytes([report_id]) + raw
        try:
            h.send_feature_report(payload)
            print(f"  Report {key} ({name}): restauré ({len(raw)}B)")
        except OSError as e:
            print(f"  Report {key} ({name}): ERREUR — {e}")

    h.close()
    print("\nRestauration terminée.")


def dump_reports(vid: int, pid: int):
    """Affiche tous les Feature Reports sans sauvegarder."""
    h = open_device(vid, pid)
    print("Lecture des Feature Reports...\n")

    for report_id, info in REPORT_IDS.items():
        try:
            data = h.get_feature_report(report_id, info["size"])
            if data:
                hex_str = " ".join(f"{b:02x}" for b in data)
                print(f"Report 0x{report_id:02x} ({info['name']}, {len(data)}B):")
                print(f"  {hex_str}")

                # Décodage pour les reports pédale
                if report_id in (0x10, 0x11, 0x12):
                    import struct
                    cal_min = struct.unpack_from("<H", bytes(data), 23)[0]
                    cal_max = struct.unpack_from("<H", bytes(data), 25)[0]
                    param_a = struct.unpack_from("<H", bytes(data), 34)[0]
                    param_b = struct.unpack_from("<H", bytes(data), 36)[0]
                    mapping = list(data[28:33])
                    print(f"  cal_min={cal_min}  cal_max={cal_max}")
                    print(f"  param_a={param_a}  param_b={param_b}")
                    print(f"  mapping={mapping}")
                print()
        except OSError as e:
            print(f"Report 0x{report_id:02x}: erreur ({e})\n")

    h.close()


def main():
    parser = argparse.ArgumentParser(description="Venym Pedals — Config Backup & Restore")
    parser.add_argument("--vid", type=lambda x: int(x, 0), default=VID)
    parser.add_argument("--pid", type=lambda x: int(x, 0), default=PID)
    parser.add_argument("--save", type=str, help="Sauvegarder dans un fichier JSON")
    parser.add_argument("--restore", type=str, help="Restaurer depuis un fichier JSON")
    parser.add_argument("--dump", action="store_true", help="Afficher les reports")

    args = parser.parse_args()

    if args.save:
        save_backup(args.save, args.vid, args.pid)
    elif args.restore:
        print("⚠ ATTENTION : ceci va écrire sur le pédalier !")
        confirm = input("Continuer ? (oui/non) : ")
        if confirm.lower() != "oui":
            print("Annulé.")
            return
        restore_backup(args.restore, args.vid, args.pid)
    elif args.dump:
        dump_reports(args.vid, args.pid)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
