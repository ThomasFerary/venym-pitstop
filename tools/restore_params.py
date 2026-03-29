#!/usr/bin/env python3
"""Restaure les paramètres originaux du pédalier."""
import struct, sys, time

VID, PID = 0x3441, 0x1501
# Valeurs originales du backup
ORIG = {
    0x10: {"pa": 600, "pb": 400},  # Accel
    0x11: {"pa": 500, "pb": 4300}, # Frein
    0x12: {"pa": 300, "pb": 100},  # Embrayage
}

import hid
h = hid.device()
h.open(VID, PID)

for rid, params in ORIG.items():
    data = h.get_feature_report(rid, 64)
    if not data or len(data) < 38:
        continue
    modified = bytearray(data)
    cur_pa = struct.unpack_from("<H", bytes(data), 34)[0]
    cur_pb = struct.unpack_from("<H", bytes(data), 36)[0]
    struct.pack_into("<H", modified, 34, params["pa"])
    struct.pack_into("<H", modified, 36, params["pb"])

    # Aussi restaurer la courbe linéaire
    linear = [20, 20, 0, 40, 40, 0, 60, 60, 0, 80, 80, 0, 100, 100, 0]
    for i, b in enumerate(linear):
        modified[8 + i] = b

    payload = bytearray(63)
    payload[0] = rid
    for i, b in enumerate(modified[:min(len(modified), 62)]):
        payload[1 + i] = b
    h.send_feature_report(bytes([rid]) + bytes(payload))
    time.sleep(0.2)

    check = h.get_feature_report(rid, 64)
    new_pa = struct.unpack_from("<H", bytes(check), 34)[0]
    new_pb = struct.unpack_from("<H", bytes(check), 36)[0]
    name = {0x10: "Accel", 0x11: "Frein", 0x12: "Emb"}[rid]
    print(f"{name}: pa {cur_pa}->{new_pa} pb {cur_pb}->{new_pb}")

h.close()
print("Restauré.")
