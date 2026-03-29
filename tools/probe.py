#!/usr/bin/env python3
"""
Venym Pedals — Feature Report Probe

Explore les Feature Reports et Output Reports du pédalier
pour trouver l'interface de configuration cachée.

Usage :
    python tools/probe.py
    python tools/probe.py --vid 0x3441 --pid 0x1501
"""

import argparse
import sys
import time

VID = 0x3441
PID = 0x1501


def probe_feature_reports(vid: int, pid: int):
    """Tente de lire des Feature Reports pour différents Report IDs."""
    import hid

    # Lister les interfaces
    interfaces = [d for d in hid.enumerate() if d["vendor_id"] == vid and d["product_id"] == pid]
    if not interfaces:
        print(f"Périphérique 0x{vid:04x}:0x{pid:04x} non trouvé.")
        sys.exit(1)

    print(f"=== Probe Feature Reports — 0x{vid:04x}:0x{pid:04x} ===\n")
    print(f"{len(interfaces)} interface(s) détectée(s)\n")

    for iface_info in interfaces:
        iface_num = iface_info.get("interface_number", -1)
        up = iface_info.get("usage_page", 0)
        print(f"--- Interface {iface_num} (Usage Page 0x{up:04x}) ---\n")

        h = hid.device()
        try:
            h.open_path(iface_info["path"])
        except OSError as e:
            print(f"  Impossible d'ouvrir : {e}\n")
            continue

        # Tester GET Feature Report pour report IDs 0x00–0x20
        print("  GET Feature Reports :")
        found_any = False
        for report_id in range(0x00, 0x21):
            for size in [8, 16, 32, 64]:
                try:
                    data = h.get_feature_report(report_id, size)
                    if data:
                        hex_str = " ".join(f"{b:02x}" for b in data)
                        print(f"    Report 0x{report_id:02x} ({size}B request): [{len(data)}B] {hex_str}")
                        found_any = True
                        break  # Pas besoin de tester d'autres tailles
                except OSError:
                    pass
                except Exception as e:
                    if "not implemented" not in str(e).lower():
                        print(f"    Report 0x{report_id:02x}: erreur {e}")
                    break

        if not found_any:
            print("    Aucun Feature Report trouvé.")

        # Tester aussi les report IDs plus élevés (vendor)
        print("\n  GET Feature Reports (vendor range 0xF0–0xFF) :")
        found_vendor = False
        for report_id in range(0xF0, 0x100):
            for size in [8, 16, 32, 64]:
                try:
                    data = h.get_feature_report(report_id, size)
                    if data:
                        hex_str = " ".join(f"{b:02x}" for b in data)
                        print(f"    Report 0x{report_id:02x} ({size}B request): [{len(data)}B] {hex_str}")
                        found_vendor = True
                        break
                except (OSError, Exception):
                    pass

        if not found_vendor:
            print("    Aucun Feature Report vendor trouvé.")

        # Lire quelques paquets input pour confirmation
        print("\n  Input Reports (5 premiers) :")
        h.set_nonblocking(1)
        count = 0
        t0 = time.time()
        while count < 5 and time.time() - t0 < 2:
            data = h.read(64)
            if data:
                hex_str = " ".join(f"{b:02x}" for b in data)
                print(f"    [{len(data)}B] {hex_str}")
                count += 1
            else:
                time.sleep(0.01)
        if count == 0:
            print("    Aucun Input Report reçu.")

        h.close()
        print()


def probe_pyusb(vid: int, pid: int):
    """Explore les descripteurs USB détaillés via pyusb."""
    try:
        import usb.core
        import usb.util
    except ImportError:
        print("pyusb non installé, skip.\n")
        return

    print(f"=== Descripteurs USB (pyusb) — 0x{vid:04x}:0x{pid:04x} ===\n")

    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        print("Non trouvé via pyusb (normal sous Windows sans libusb).\n")
        return

    print(dev)
    print()

    # Lister les configurations et interfaces
    for cfg in dev:
        print(f"Configuration {cfg.bConfigurationValue}:")
        for intf in cfg:
            print(f"  Interface {intf.bInterfaceNumber} alt {intf.bAlternateSetting}:")
            print(f"    Class: 0x{intf.bInterfaceClass:02x} SubClass: 0x{intf.bInterfaceSubClass:02x}")
            print(f"    Protocol: 0x{intf.bInterfaceProtocol:02x}")
            for ep in intf:
                direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
                print(f"    Endpoint 0x{ep.bEndpointAddress:02x} {direction} "
                      f"MaxPacket={ep.wMaxPacketSize} Interval={ep.bInterval}")

    # Tenter de lire le HID Report Descriptor
    print("\n=== HID Report Descriptor ===\n")
    for intf_num in range(4):
        try:
            # HID descriptor: bmRequestType=0x81 (device-to-host, standard, interface)
            # bRequest=0x06 (GET_DESCRIPTOR), wValue=0x2200 (HID Report Descriptor)
            desc = dev.ctrl_transfer(0x81, 0x06, 0x2200, intf_num, 256)
            hex_str = " ".join(f"{b:02x}" for b in desc)
            print(f"  Interface {intf_num}: [{len(desc)}B] {hex_str}")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Venym Pedals — Feature Report Probe")
    parser.add_argument("--vid", type=lambda x: int(x, 0), default=VID)
    parser.add_argument("--pid", type=lambda x: int(x, 0), default=PID)
    args = parser.parse_args()

    probe_feature_reports(args.vid, args.pid)
    probe_pyusb(args.vid, args.pid)

    print("=== Probe terminé ===")


if __name__ == "__main__":
    main()
