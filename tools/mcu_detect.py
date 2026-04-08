#!/usr/bin/env python3
"""
Venym Pedals — MCU Detection

Tente d'identifier le MCU par :
1. Descripteurs USB détaillés
2. Réponse à des commandes DFU standard
3. Réponse à des control transfers spécifiques aux bootloaders
4. Scan des VID/PID DFU connus après reset
"""
import sys
import struct
import time

VID = 0x3441
PID = 0x1501


def main():
    import libusb_package
    import usb.core
    import usb.backend.libusb1
    import hid

    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)

    if not dev:
        print("Pedalier non trouve")
        return

    print("=== Identification MCU ===\n")

    # 1. Descripteurs USB détaillés
    print(f"VID: 0x{dev.idVendor:04x}  PID: 0x{dev.idProduct:04x}")
    print(f"bcdDevice: 0x{dev.bcdDevice:04x} (v{dev.bcdDevice >> 8}.{dev.bcdDevice & 0xFF:02d})")
    print(f"bcdUSB: 0x{dev.bcdUSB:04x}")
    print(f"bMaxPacketSize0: {dev.bMaxPacketSize0}")
    print(f"Manufacturer: {dev.manufacturer}")
    print(f"Product: {dev.product}")
    print(f"Serial: {dev.serial_number}")
    print()

    # 2. Device Qualifier descriptor (USB 2.0 high-speed capable?)
    print("=== Device Qualifier ===")
    try:
        dq = dev.ctrl_transfer(0x80, 0x06, 0x0600, 0, 10)
        print(f"  Device Qualifier: {' '.join(f'{b:02x}' for b in dq)}")
        print(f"  -> Device supporte High-Speed (rare pour MCU bas cout)")
    except:
        print("  Pas de Device Qualifier (Full-Speed only = MCU typique)")

    # 3. Tenter de lire des vendor-specific descriptors
    print("\n=== Vendor-specific control transfers ===")
    # STM32 bootloader utilise bmRequestType=0xA1 (device-to-host, class, interface)
    # AT32 bootloader est compatible STM32
    for req_type, req, wValue, wIndex, desc in [
        (0xC0, 0x00, 0, 0, "Vendor GET (generic)"),
        (0xC0, 0x01, 0, 0, "Vendor GET cmd 1"),
        (0xC0, 0xFF, 0, 0, "Vendor GET cmd FF"),
        (0xA1, 0x03, 0, 0, "DFU GETSTATUS"),
        (0xA1, 0x05, 0, 0, "DFU GETSTATE"),
        (0x80, 0x06, 0x0300, 0, "String descriptor lang"),
    ]:
        try:
            data = dev.ctrl_transfer(req_type, req, wValue, wIndex, 64, timeout=500)
            if data:
                print(f"  {desc}: [{len(data)}B] {' '.join(f'{b:02x}' for b in data)}")
        except Exception as e:
            err = str(e)
            if "timeout" in err.lower():
                print(f"  {desc}: timeout")
            elif "pipe" in err.lower() or "stall" in err.lower():
                pass  # STALL = pas supporte, normal
            else:
                pass

    # 4. Lire tous les string descriptors possibles
    print("\n=== String descriptors (0-20) ===")
    import usb.util
    for idx in range(21):
        try:
            s = usb.util.get_string(dev, idx)
            if s and len(s) > 0:
                print(f"  [{idx}] = '{s}'")
        except:
            pass

    # 5. Essayer de lire la flash via des Feature Reports inconnus
    print("\n=== Feature Reports etendus (HID) ===")
    h = hid.device()
    h.open(VID, PID)

    found_reports = []
    for rid in range(0, 256):
        try:
            data = h.get_feature_report(rid, 64)
            if data and len(data) > 0:
                hex_str = ' '.join(f'{b:02x}' for b in data[:20])
                suffix = "..." if len(data) > 20 else ""
                found_reports.append(rid)
                if rid not in [0x03, 0x05, 0x10, 0x11, 0x12]:  # Skip connus
                    print(f"  Report 0x{rid:02x}: [{len(data)}B] {hex_str}{suffix}")
        except:
            pass

    print(f"\n  Reports trouves: {[f'0x{r:02x}' for r in found_reports]}")

    # 6. Byte[1]=1 mode — tester plus de valeurs
    print("\n=== Byte [1] modes speciaux ===")
    r10 = bytes(h.get_feature_report(0x10, 64))
    for val in [0, 1, 2, 3, 4, 0x10, 0x20, 0x40, 0x80, 0xAA, 0xFF]:
        modified = bytearray(r10)
        modified[1] = val
        payload = bytearray(63)
        payload[0] = 0x10
        for i, b in enumerate(modified[:62]):
            payload[1+i] = b
        h.send_feature_report(bytes([0x10]) + bytes(payload))
        time.sleep(0.1)
        check = bytes(h.get_feature_report(0x10, 64))
        # Lire un input report
        h.set_nonblocking(1)
        time.sleep(0.05)
        inp = h.read(64)
        h.set_nonblocking(0)
        accel = (inp[1] | (inp[2] << 8)) if inp and len(inp) >= 3 else 0
        print(f"  byte[1]=0x{val:02x}: accel_input={accel}")

    # Restaurer
    payload_restore = bytearray(63)
    payload_restore[0] = 0x10
    for i, b in enumerate(r10[:62]):
        payload_restore[1+i] = b
    h.send_feature_report(bytes([0x10]) + bytes(payload_restore))

    h.close()

    # 7. Indices du VID
    print("\n=== Analyse VID 0x3441 ===")
    print(f"  Decimal: {0x3441}")
    print(f"  Pas dans les registres USB-IF publics")
    print(f"  MCU chinois courants avec VID custom:")
    print(f"    AT32 (Artery): VID DFU = 0x2E3C")
    print(f"    GD32 (GigaDevice): VID DFU = 0x28E9")
    print(f"    STM32 (ST): VID DFU = 0x0483")
    print(f"    CH32 (WCH): VID = 0x1A86")
    print(f"    APM32 (Geehy): VID DFU = 0x314B")
    print()
    print("  Pour identifier: ouvrir le boitier et lire le marquage MCU")
    print("  Ou: trouver le mode DFU et lire le VID/PID du bootloader")


if __name__ == "__main__":
    main()
