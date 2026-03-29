#!/usr/bin/env python3
"""Debug complet : compare r05 (ADC brut) vs Input Report pour comprendre la DZ."""
import hid, struct, time

VID = 0x3441
PID = 0x1501

h = hid.device()
h.open(VID, PID)
h.set_nonblocking(1)

# Lire config actuelle
d = bytes(h.get_feature_report(0x10, 64))
cal_min = struct.unpack_from('<H', d, 23)[0]
cal_max = struct.unpack_from('<H', d, 25)[0]
pa = struct.unpack_from('<H', d, 34)[0]
print(f"Config: cal_min={cal_min} cal_max={cal_max} pa={pa} ({pa/100:.1f}%)")
print(f"cal_range={cal_max - cal_min}")
print()

def write_pa(h, orig_data, new_pa):
    modified = bytearray(orig_data)
    struct.pack_into('<H', modified, 34, new_pa)
    payload = bytearray(63)
    payload[0] = 0x10
    for i, b in enumerate(modified[:62]):
        payload[1+i] = b
    h.send_feature_report(bytes([0x10]) + bytes(payload))
    time.sleep(0.3)

def read_both(h):
    """Lit r05 et Input Report simultanément."""
    r05 = bytes(h.get_feature_report(0x05, 64))
    adc_brut = struct.unpack_from('<H', r05, 0)[0]

    # Lire quelques input reports
    vals = []
    t0 = time.time()
    while time.time() - t0 < 0.3:
        data = h.read(64)
        if data and len(data) >= 5:
            vals.append(data[1] | (data[2] << 8))
        else:
            time.sleep(0.001)

    input_val = sorted(vals)[len(vals)//2] if vals else 0
    return adc_brut, input_val

print("=== Ne touche pas la pedale ===")
print(f"{'pa':>6s}  {'r05 brut':>9s}  {'Input':>7s}  {'Input-r05':>10s}  {'Input%':>7s}  {'(I-calmin)/range':>16s}")

for test_pa in [0, 50, 100, 200, 300, 500, 600, 1000, 2000]:
    write_pa(h, d, test_pa)
    r05, inp = read_both(h)
    diff = inp - r05
    inp_pct = (inp - cal_min) / (cal_max - cal_min) * 100
    print(f"{test_pa:6d}  {r05:9d}  {inp:7d}  {diff:10d}  {inp_pct:6.1f}%  offset/pa={diff/test_pa:.3f}" if test_pa > 0 else f"{test_pa:6d}  {r05:9d}  {inp:7d}  {diff:10d}  {inp_pct:6.1f}%")

# Restaurer
write_pa(h, d, pa)
print()

print("=== Appuie a FOND et maintiens ===")
input("Enter...")

for test_pa in [0, 100, 300, 600, 1000]:
    write_pa(h, d, test_pa)
    r05, inp = read_both(h)
    diff = inp - r05
    inp_pct = (inp - cal_min) / (cal_max - cal_min) * 100
    print(f"  pa={test_pa:5d}: r05={r05}  input={inp}  diff={diff}  pct={inp_pct:.1f}%")

write_pa(h, d, pa)
print("Relache.")
time.sleep(1)
print()

# Test: que se passe-t-il si cal_min = valeur repos post-offset ?
print("=== Test: cal_min = valeur repos avec offset ===")
# D'abord, mesurer le repos avec pa courant
write_pa(h, d, pa)
_, repos_input = read_both(h)
print(f"Repos avec pa={pa}: input={repos_input}")

# Maintenant, mettre cal_min = repos_input
modified = bytearray(d)
struct.pack_into('<H', modified, 23, repos_input)
payload = bytearray(63)
payload[0] = 0x10
for i, b in enumerate(modified[:62]):
    payload[1+i] = b
h.send_feature_report(bytes([0x10]) + bytes(payload))
time.sleep(0.3)

_, new_repos = read_both(h)
new_pct = (new_repos - repos_input) / (cal_max - repos_input) * 100
print(f"Apres cal_min={repos_input}: input repos={new_repos}  pct={new_pct:.1f}%")

# Restaurer original
write_pa(h, d, pa)
payload2 = bytearray(63)
payload2[0] = 0x10
for i, b in enumerate(d[:62]):
    payload2[1+i] = b
h.send_feature_report(bytes([0x10]) + bytes(payload2))
time.sleep(0.2)

h.close()
print("\nConfig restauree.")
