#!/usr/bin/env python3
"""
SAMD21 Bootloader Detection

Le ATSAMD21 a un bootloader ROM (SAM-BA) accessible via :
1. Double-reset (double-tap sur bouton reset du PCB)
2. Commande USB spécifique dans certains firmwares
3. Bootloader UF2 si installé

Ce script :
- Tente de trigger le bootloader via USB
- Scanne les VID/PID connus des bootloaders SAMD21
- Guide l'utilisateur pour le double-reset
"""
import sys
import time

SAMD21_BOOTLOADER_VIDS_PIDS = [
    (0x03EB, 0x6124, "Atmel SAM-BA"),
    (0x239A, 0x0015, "Adafruit UF2 SAMD21"),
    (0x239A, 0x000B, "Adafruit Feather M0"),
    (0x2341, 0x004D, "Arduino Zero bootloader"),
    (0x2341, 0x824D, "Arduino Zero bootloader (alt)"),
    (0x1B4F, 0x0D22, "SparkFun SAMD21"),
    (0x1209, 0x2017, "Generic UF2 SAMD21"),
]


def scan_bootloaders():
    """Scanne tous les USB devices pour trouver un bootloader SAMD21."""
    import libusb_package
    import usb.core
    import usb.backend.libusb1

    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)

    print("Scan des bootloaders SAMD21 connus...")
    found = False

    # Scanner TOUS les devices USB
    devices = usb.core.find(find_all=True, backend=backend)
    for dev in devices:
        vid, pid = dev.idVendor, dev.idProduct
        # Check contre les bootloaders connus
        for bvid, bpid, name in SAMD21_BOOTLOADER_VIDS_PIDS:
            if vid == bvid and pid == bpid:
                print(f"  TROUVE: {name} (VID=0x{vid:04x} PID=0x{pid:04x})")
                found = True

        # Aussi checker si c'est un device DFU generique
        try:
            for cfg in dev:
                for intf in cfg:
                    if intf.bInterfaceClass == 0xFE and intf.bInterfaceSubClass == 0x01:
                        print(f"  TROUVE: DFU device VID=0x{vid:04x} PID=0x{pid:04x}")
                        try:
                            print(f"    Manufacturer: {dev.manufacturer}")
                            print(f"    Product: {dev.product}")
                        except:
                            pass
                        found = True
        except:
            pass

    if not found:
        print("  Aucun bootloader SAMD21 detecte")

    return found


def try_usb_reset():
    """Tente un USB reset qui pourrait trigger le bootloader."""
    import libusb_package
    import usb.core
    import usb.backend.libusb1

    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    dev = usb.core.find(idVendor=0x3441, idProduct=0x1501, backend=backend)

    if not dev:
        print("Pedalier non trouve")
        return

    print("Tentative de reset USB...")
    try:
        dev.reset()
        print("  Reset envoye")
    except Exception as e:
        print(f"  Reset: {e}")


def main():
    print("=== ATSAMD21E18A Bootloader Detection ===\n")

    # D'abord scanner les bootloaders existants
    scan_bootloaders()
    print()

    # Tenter un reset USB
    try_usb_reset()
    print()

    # Attendre et rescanner
    print("Attente 3 secondes apres reset...")
    time.sleep(3)
    found = scan_bootloaders()
    print()

    if not found:
        print("=== Methode manuelle ===")
        print()
        print("Le SAMD21 entre en mode bootloader par DOUBLE-RESET :")
        print("  1. Localise le bouton RESET sur le PCB du pedalier")
        print("     (petit bouton tactile, souvent marque RST)")
        print("  2. Appuie rapidement 2 fois (double-tap)")
        print("  3. Le pedalier devrait apparaitre comme un nouveau device USB")
        print()
        print("Ou par le pad BOOT0 :")
        print("  1. Court-circuite le pad BOOT0 a GND")
        print("  2. Branche le USB")
        print("  3. Le bootloader SAM-BA demarre")
        print()
        input("Si tu as fait le double-reset, appuie Enter pour rescanner...")
        scan_bootloaders()


if __name__ == "__main__":
    main()
