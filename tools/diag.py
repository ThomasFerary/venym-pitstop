#!/usr/bin/env python3
"""Diagnostic rapide : appuie progressivement sur l'accélérateur."""
import hid, struct, time

h = hid.device()
h.open(0x3441, 0x1501)
h.set_nonblocking(1)

d = bytes(h.get_feature_report(0x10, 64))
cal_min = struct.unpack_from('<H', d, 23)[0]
cal_max = struct.unpack_from('<H', d, 25)[0]
print(f'cal_min={cal_min} cal_max={cal_max} range={cal_max-cal_min}')
print()
input("Appuie Enter puis fais un aller-retour LENT sur l'accélérateur (6s)...")

t0 = time.time()
last = 0
while time.time() - t0 < 6:
    data = h.read(64)
    if data and len(data) >= 5:
        accel = data[1] | (data[2] << 8)
        elapsed = time.time() - t0
        if elapsed - last >= 0.15:
            pct = (accel - cal_min) / (cal_max - cal_min) * 100
            bar = '#' * max(0, int(pct / 2))
            print(f'[{elapsed:4.1f}s] ADC={accel:5d}  {pct:6.1f}% |{bar}')
            last = elapsed
    else:
        time.sleep(0.001)
h.close()
