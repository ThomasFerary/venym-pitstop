# Venym Atrax — USB Protocol Documentation

Résultat du reverse engineering complet du protocole USB HID du pédalier Venym Atrax.
Testé sur firmware version 1.13.

## Périphérique

| Champ          | Valeur                           |
|----------------|----------------------------------|
| VID            | `0x3441`                         |
| PID            | `0x1501`                         |
| Fabricant      | Venym                            |
| Produit        | Venym Atrax                      |
| USB            | 2.0, 500 mA                      |
| Interface      | 1 seule (HID, Usage Page 0x0001) |
| Endpoints      | 0x81 IN (64B) + 0x02 OUT (64B)  |
| Pédales        | 2 (accélérateur + frein), embrayage optionnel |

### HID Report Descriptor (33 bytes)

```
Usage Page: Generic Desktop (0x0001)
Usage: Joystick (0x04)
Collection: Application
  Input:   6 bytes × 8 bits (axes)
  Feature: 63 bytes × 8 bits (configuration, Buffered Bytes)
End Collection
```

Pas de Report ID dans le descriptor. Le firmware utilise le premier byte du Feature Report comme sélecteur interne.

---

## Input Report — Axes (7B, ~500 Hz)

Envoyé en continu sur l'endpoint IN. Contient les valeurs **post-traitement** (après application de la courbe, dead zone et offset par le firmware).

```
Offset  Type        Description
------  ----------  ----------------------------
0       uint8       Report ID (toujours 0x01)
1-2     uint16 LE   Accélérateur (valeur traitée)
3-4     uint16 LE   Frein (valeur traitée)
5       uint8       Constant 0x30 (identifiant modèle)
6       uint8       Constant 0x0C (identifiant modèle)
```

Les valeurs de sortie sont bornées par le firmware :
- **Repos** : `cal_min + offset(param_a)` (ex: 2291 + 145 = 2436)
- **Fond** : plafond firmware à ~96% du range de calibration (ex: 4612)

---

## Feature Reports — Configuration

### Report 0x03 — Info firmware (9B, lecture seule)

```
Offset  Type        Description
------  ----------  ----------------------------
0       uint8       Nombre de pédales (= 2)
1-3     3 bytes     Identifiant firmware
4-6     3 bytes     Réservé (0x00)
7-8     uint16 LE   Build number (= 9000)
```

### Report 0x05 — ADC temps réel (7B, lecture)

Miroir temps réel des valeurs ADC **brutes** (avant traitement firmware).

```
Offset  Type        Description
------  ----------  ----------------------------
0-1     uint16 LE   ADC brut accélérateur
2-3     uint16 LE   ADC brut frein
4-5     uint16 LE   ADC brut embrayage (0 si non connecté)
6       uint8       Bruit ADC / résidu multiplexage (NON persistant)
```

Ce report retourne 7 bytes (et non 6). Le byte 6 fluctue en permanence entre des valeurs
comme 0x00, 0x57, 0x5c, 0x61, 0x64, 0x65 — même au repos. C'est du bruit ADC ou un
artefact du multiplexeur analogique, **pas un setting persistant**.

Ce report est le seul writable via `send_feature_report`, mais les valeurs sont immédiatement écrasées par l'ADC.

### Global Settings & LED Colors — NON présents dans le firmware

Les réglages globaux visibles dans l'ancienne app (inversion pédales, seuil flicker LEDs,
intensité max LEDs, couleurs LED) ne sont stockés dans **aucun Feature Report** du firmware.
Un probe exhaustif des reports 0x00–0x20 et 0xF0–0xFF ne révèle aucun report inconnu.
Les 38 bytes des reports 0x10–0x12 sont entièrement documentés sans espace libre.

**Conclusion** : ces settings étaient gérés côté logiciel par l'ancienne app Venym Pitstop
(probablement dans le registre Windows ou un fichier de configuration local).
Notre implémentation les persiste dans les profils JSON.

### Reports 0x10 / 0x11 / 0x12 — Configuration pédale (38B)

`0x10` = Accélérateur, `0x11` = Frein, `0x12` = Embrayage

```
Offset  Type        Description                              Valeur exemple (accel)
------  ----------  ---------------------------------------- ---------------------
 0      uint8       Version config                           0x04
 1      uint8       Mode flag (bit 0 = bypass courbe?)       0x00
 2      uint8       Pedal type (0x00=hall, 0x10=load cell)   0x00
 3      uint8       Enabled                                  0x01
 4      uint8       Nombre de points courbe (5+1 implicite)  0x06
 5      uint8       Réservé                                  0x00
 6      uint8       Point courbe implicite y1 (x=0%)         0x00
 7      uint8       Réservé                                  0x00

 8-22   15 bytes    Courbe de réponse (5 triplets)           voir ci-dessous

23-24   uint16 LE   Calibration ADC min                      2291
25-26   uint16 LE   Calibration ADC max                      4708
27      uint8       Réservé                                  0x00

28-32   5 bytes     Mapping physique pédales                 [0,0,0xFF,0,0]

33      uint8       Max output (toujours 100)                100

34-35   uint16 LE   Dead zone basse (param_a)                600
36-37   uint16 LE   Force/sensibilité (param_b)              400
```

---

## Courbe de réponse — bytes [8:22]

### Format

5 triplets de 3 octets. Le point (0%, 0%) est implicite (byte [6]).

```
Triplet : [input%, y1, y2]

Byte 0 : input%  — position d'entrée (typiquement 20, 40, 60, 80, 100)
Byte 1 : y1      — paramètre de sortie (voir LUT ci-dessous)
Byte 2 : y2      — poids d'interpolation (0x00 = défaut, 0x80/0x40 = tangentes)
```

### Mapping y1 → sortie effective

**Le y1 n'est PAS un pourcentage direct.** C'est un index dans une LUT non-linéaire du firmware. Mapping mesuré expérimentalement :

| y1  | Sortie effective |
|-----|-----------------|
| 0   | 0%              |
| 50  | ~0%             |
| 60  | ~1%             |
| 70  | ~6%             |
| 77  | ~20%            |
| 80  | ~32%            |
| 81  | ~40%            |
| 83  | ~56%            |
| 85  | ~83%            |
| 86  | ~92%            |
| 87  | ~96% (plafond)  |
| 88+ | ~96% (saturé)   |
| 127 | OVERFLOW (bug)  |
| 200+ | 0% (invalide)  |

**Plage utile : 60–87.** Au-delà de 87, la sortie plafonne à 96% du range ADC.

### Courbe par défaut (linéaire)

```
(20, 77, 0)  → input 20% → output ~20%
(40, 81, 0)  → input 40% → output ~40%
(60, 83, 128) → input 60% → output ~56%
(80, 85, 0)  → input 80% → output ~83%
(100, 86, 64) → input 100% → output ~92%
```

Cette courbe produit une progression quasi-linéaire de la pédale. La sortie max est ~92% (y1=86), pas 96%.

### Valeurs interdites

- **y1=127 (0x7F)** : cause un overflow (sortie = 16696 ADC)
- **x=0** pour un point explicite : overflow
- **y1 ≥ 200** : sortie retombe à 0%

---

## Dead zone basse — param_a [34:35]

Offset appliqué par le firmware à la valeur de repos. **Relation linéaire confirmée :**

```
1% de dead zone = param_a de 100
```

| param_a | Sortie repos | Dead zone effective |
|---------|-------------|-------------------|
| 0       | 0.2%        | 0%                |
| 100     | 1.0%        | 1%                |
| 300     | 3.0%        | 3%                |
| 500     | 5.0%        | 5%                |
| 600     | 6.0%        | 6%                |
| 1000    | 10.0%       | 10%               |

**Attention :** param_a=0 peut causer un comportement erratique (la sortie saute à 96%). Valeur minimum recommandée : 50 (0.5%).

Le param_a n'affecte PAS la sortie à fond (toujours le plafond firmware).

Valeurs observées dans l'ancienne app (screenshot) :
- Accélérateur : Lower deadzone 1.00% → param_a = 100
- Frein : Lower deadzone 5.00% → param_a = 500
- Embrayage : Lower deadzone 3.00% → param_a = 300

---

## Dead zone haute — y2 du dernier point de courbe — CONFIRMÉ

Le byte y2 du **dernier point** de courbe (point 5, x=100%) contrôle la dead zone haute.

```
DZ haute (%) = y2 / 32
y2 = DZ haute (%) * 32
```

| y2  | DZ haute | Max sortie | Effet                             |
|-----|----------|-----------|-----------------------------------|
| 0   | 0%       | 92.4%     | Pas de saturation en fin de course |
| 32  | 1%       | 94.2%     | Saturation légère                 |
| 64  | 2%       | 96.0%     | Atteint le plafond firmware       |
| 96  | 3%       | 96.0%     | Plafond atteint plus tôt          |
| 128 | 4%       | 96.0%     | Plafond atteint encore plus tôt   |
| 160 | 5%       | 96.0%     | Large zone de saturation          |

**Note :** y2=64 (2% DZ haute) est la valeur par défaut qui permet d'atteindre le plafond firmware (96% du range ADC).
Sans DZ haute (y2=0), la sortie ne dépasse jamais 92.4%.

Les bytes y2 des **autres points** (intermédiaires) semblent contrôler la tangente d'interpolation cubique.
La valeur y2=128 (0x80) est observée sur le point central (x=60%) dans la courbe par défaut.

---

## Force/sensibilité frein — param_b [36:37]

Contrôle la sensibilité du load cell (capteur de pression) du frein. Plus la valeur est haute, plus il faut appuyer fort pour atteindre le maximum.

| param_b | Effet                                    |
|---------|------------------------------------------|
| 0       | Load cell désactivé (sortie = 0)         |
| 500     | Très sensible (7% à fond)                |
| 1000    | Sensible (14% à fond)                    |
| 4300    | Force élevée (~60 kg estimé)             |

Conversion approximative : **1 kg ≈ 45–46 units** (basé sur screenshot ancienne app : 94.4 kg ≈ 4300).

Pour l'accélérateur (capteur hall), param_b n'a pas d'effet visible. Valeur typique : 400.

---

## Mapping physique — bytes [28:32]

5 positions de connecteur sur le PCB. Un seul `0xFF` par report indique quelle position physique correspond à cette pédale logique.

| Position | Pédale        |
|----------|--------------|
| 0        | Frein         |
| 1        | (libre)       |
| 2        | Accélérateur  |
| 3        | (libre)       |
| 4        | Embrayage     |

---

## Écriture de la configuration

### Format

```
send_feature_report(payload) où :
  payload[0]     = report_id (transport HID, ex: 0x10)
  payload[1]     = report_id (sélecteur pédale, identique)
  payload[2:40]  = données config (38 bytes)
  payload[40:64] = padding 0x00
  Total = 64 bytes
```

### Procédure

1. Lire la config actuelle via `get_feature_report(report_id, 64)`
2. Modifier les bytes souhaités
3. Écrire via `send_feature_report()` avec le format ci-dessus
4. Relire pour confirmer

Les modifications sont **persistées en flash** — elles survivent au débranchement.

### Notes importantes

- Toujours lire avant d'écrire pour préserver les bytes inconnus
- Les reports 0x10/0x11/0x12 ne supportent PAS le SET_REPORT classique via control transfer — seul `send_feature_report` de hidapi fonctionne
- Le report 0x05 est le seul qui accepte aussi l'écriture directe, mais c'est inutile (ADC temps réel)

---

## Byte [1] — Mode flag

| Valeur | Effet                                        |
|--------|----------------------------------------------|
| 0      | Normal                                       |
| 1, 3, 5, 7, 9... (impair) | Sortie = cal_min exact (bypass offset) |
| 2, 4, 6, 8, 10... (pair)  | Normal                            |

Le bit 0 semble être un flag de calibration/bypass.

## Byte [6] — Point courbe implicite (x=0%)

Même mapping LUT que les y1 de la courbe. Quand modifié, affecte la sortie au repos.
Valeur par défaut : 0 (pas d'effet).
Valeur 100 → sortie bloquée à 96% même au repos.

---

## Résumé pour l'implémentation

### Lecture d'une pédale

```python
data = device.get_feature_report(0x10, 64)  # 38 bytes
cal_min = uint16_le(data[23:25])
cal_max = uint16_le(data[25:27])
param_a = uint16_le(data[34:36])  # dead zone basse (100 = 1%)
param_b = uint16_le(data[36:38])  # force frein
curve = [(data[8+i*3], data[8+i*3+1], data[8+i*3+2]) for i in range(5)]
```

### Normalisation de la sortie (Input Report)

```python
# Le firmware applique courbe + offset. Pour afficher 0-100% :
effective_min = cal_min + param_a * 0.241
effective_max = cal_max - (cal_max - cal_min) * 0.04
ratio = (adc_value - effective_min) / (effective_max - effective_min)
display_pct = clamp(ratio, 0, 1) * 100
```

### Conversion courbe UI ↔ firmware

```python
# UI → firmware : output% (0.0-1.0) → y1 (60-87)
# Utiliser la LUT d'interpolation inverse

# firmware → UI : y1 (60-87) → output% (0.0-1.0)
# Normaliser par le y1 max du dernier point
```
