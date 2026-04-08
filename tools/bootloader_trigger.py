#!/usr/bin/env python3
"""
Tente de trigger le bootloader SAMD21 via des commandes USB.

Le firmware Venym a probablement une commande cachée pour rebooter
en mode bootloader (SAM-BA). L'ancienne app l'utilisait pour flasher.

ATTENTION : si le bootloader démarre, le pédalier disparaît du HID
et réapparaît comme un nouveau device. C'est réversible.
"""
import sys
import time
import struct

VID = 0x3441
PID = 0x1501

# Bootloaders SAMD21 connus
BOOTLOADER_VIDS = [
    (0x03EB, 0x6124, "SAM-BA"),
    (0x239A, None, "Adafruit UF2"),
    (0x2341, None, "Arduino"),
    (0x3441, None, "Venym custom bootloader"),
]


def scan_all_usb():
    """Liste tous les USB devices."""
    import libusb_package
    import usb.core
    import usb.backend.libusb1
    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    devices = list(usb.core.find(find_all=True, backend=backend))
    return [(d.idVendor, d.idProduct) for d in devices]


def scan_hid():
    """Liste tous les HID devices."""
    import hid
    return [(d["vendor_id"], d["product_id"], d.get("product_string", ""))
            for d in hid.enumerate()]


def main():
    import hid

    print("=== Tentative de trigger bootloader SAMD21 ===\n")

    # Snapshot des devices avant
    usb_before = set(scan_all_usb())
    hid_before = set((v, p) for v, p, _ in scan_hid())
    print(f"USB devices avant: {len(usb_before)}")
    print(f"HID devices avant: {len(hid_before)}")
    print()

    # Ouvrir le pédalier
    h = hid.device()
    h.open(VID, PID)

    # === Méthode 1 : Feature Report avec commande spéciale ===
    print("Methode 1: Feature Reports commande bootloader")
    boot_commands = [
        # Report ID + magic bytes courants pour SAMD21
        (0x00, bytes([0x00, 0x42, 0x4F, 0x4F, 0x54])),  # "BOOT"
        (0x00, bytes([0x00, 0x44, 0x46, 0x55])),          # "DFU"
        (0x00, bytes([0x00, 0xFF])),
        (0x00, bytes([0x00, 0xFE])),
        (0x03, bytes([0x03, 0x42, 0x4F, 0x4F, 0x54])),   # Report 0x03 + "BOOT"
        (0x03, bytes([0x03, 0xFF])),
    ]

    for rid, cmd in boot_commands:
        try:
            h.send_feature_report(cmd.ljust(64, b'\x00'))
            time.sleep(0.5)
            # Vérifier si le device a disparu
            try:
                h.get_feature_report(0x03, 64)
            except:
                print(f"  Report 0x{rid:02x} cmd={cmd[:5].hex()}: DEVICE DISPARU — bootloader?")
                h.close()
                time.sleep(2)
                usb_after = set(scan_all_usb())
                new_devices = usb_after - usb_before
                if new_devices:
                    print(f"  Nouveaux devices USB: {[(f'0x{v:04x}', f'0x{p:04x}') for v, p in new_devices]}")
                return
        except:
            pass
    print("  Aucun effet")
    print()

    # === Méthode 2 : Write (Output Report) avec magic bytes ===
    print("Methode 2: Output Reports commande bootloader")
    write_commands = [
        bytes([0x00, 0x42, 0x4F, 0x4F, 0x54]),  # "BOOT"
        bytes([0x00, 0x44, 0x46, 0x55]),          # "DFU"
        bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF]),
        bytes([0x00, 0xAA, 0x55, 0xAA, 0x55]),    # Magic pattern
        bytes([0x00, 0xDE, 0xAD, 0xBE, 0xEF]),    # deadbeef
        bytes([0x00, 0x52, 0x45, 0x42, 0x4F, 0x4F, 0x54]),  # "REBOOT"
    ]

    for cmd in write_commands:
        try:
            h.write(cmd)
            time.sleep(0.5)
            try:
                h.get_feature_report(0x03, 64)
            except:
                print(f"  Write cmd={cmd[:6].hex()}: DEVICE DISPARU — bootloader?")
                h.close()
                time.sleep(2)
                usb_after = set(scan_all_usb())
                new_devices = usb_after - usb_before
                if new_devices:
                    print(f"  Nouveaux devices: {[(f'0x{v:04x}', f'0x{p:04x}') for v, p in new_devices]}")
                return
        except:
            pass
    print("  Aucun effet")
    print()

    # === Méthode 3 : Feature Report sur des IDs non standard ===
    print("Methode 3: Feature Reports IDs inhabituels")
    for rid in [0xF0, 0xF1, 0xFE, 0xFF, 0xBB, 0xCC, 0xDD]:
        try:
            h.send_feature_report(bytes([rid, 0x01]).ljust(64, b'\x00'))
            time.sleep(0.3)
            try:
                h.get_feature_report(0x03, 64)
            except:
                print(f"  Report 0x{rid:02x}: DEVICE DISPARU!")
                h.close()
                time.sleep(2)
                usb_after = set(scan_all_usb())
                new_devices = usb_after - usb_before
                if new_devices:
                    print(f"  Nouveaux devices: {[(f'0x{v:04x}', f'0x{p:04x}') for v, p in new_devices]}")
                return
        except:
            pass
    print("  Aucun effet")

    h.close()
    print()
    print("=== Aucune commande n'a trigger le bootloader ===")
    print()
    print("Options restantes:")
    print("  1. Double-tap reset (si bouton accessible sous le PCB)")
    print("  2. Court-circuiter BOOT pin a GND au branchement")
    print("  3. Programmeur SWD via J6 (~5 EUR pour un ST-Link clone)")
    print("  4. Chercher les archives de pitstop.venym.com/flash.php")


if __name__ == "__main__":
    main()
