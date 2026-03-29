# Venym Pitstop — Spec technique

## Contexte

Venym est une marque française de pédaliers SimRacing (Atrax, Black Widow) qui a déposé bilan.
L'application officielle **Venym Pitstop** n'est plus disponible. L'objectif est de reverse engineer
le protocole USB et de recréer une application open source pour la communauté.

Le pédalier fonctionne de manière autonome (les réglages sont stockés sur l'appareil).
L'app n'est requise que pour modifier la configuration.

### Hardware connu

- Microcontrôleur 48 MHz
- ADC 20 bits par pédale (3 pédales : accélérateur, frein, embrayage)
- Connexion USB (protocole à déterminer — probablement HID)
- Ancienne app : Windows 10 uniquement
- Logs ancienne app : `C:\Users\Public\Documents\Venym\FlashLog-*.txt`

---

## Phase 1 — Reverse engineering du protocole USB (priorité absolue)

### Objectif

Identifier la structure des paquets USB échangés entre le PC et le pédalier lors de la configuration.

### Stack recommandé

- **Python** pour le prototypage rapide
- `hid` ou `hidapi` pour communiquer avec le périphérique
- `pyusb` en alternative si HID ne suffit pas

### Étapes

#### 1.1 Identifier le périphérique

```python
import hid

for device in hid.enumerate():
    print(f"VID: {device['vendor_id']:04x}  PID: {device['product_id']:04x}  {device['product_string']}")
```

Trouver le VID/PID correspondant au pédalier Venym.

#### 1.2 Lire les descripteurs HID

```python
import usb.core

dev = usb.core.find(idVendor=0xXXXX, idProduct=0xXXXX)
print(dev)
```

Chercher des "vendor-defined usages" dans les descripteurs — ils trahissent souvent le protocole de config.

#### 1.3 Lire les données brutes en temps réel

```python
import hid

h = hid.device()
h.open(VID, PID)
h.set_nonblocking(1)

while True:
    data = h.read(64)
    if data:
        print(data)
```

Observer les valeurs lors de l'appui sur chaque pédale pour identifier comment les axes sont encodés.

#### 1.4 Capturer le trafic de configuration (si l'app est retrouvée)

Utiliser **Wireshark + USBPcap** (Windows) pendant que l'ancienne app envoie une configuration.
Filtrer sur le VID/PID du pédalier. Chercher les patterns lors de :
- Changement d'un point de courbe
- Modification d'une dead zone
- Sauvegarde sur le périphérique

#### 1.5 Documenter le protocole

Créer un fichier `protocol.md` avec :
- Structure d'un paquet (header, commande, payload, checksum éventuel)
- Table des commandes identifiées
- Encodage des valeurs (float, int16, little/big endian, etc.)

---

## Phase 2 — Application de configuration

### Stack

Choisir selon les résultats de la Phase 1 :

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| **Python + CustomTkinter** | Rapide, même stack que le RE | UI moins moderne |
| **Python + Dear PyGui** | UI moderne, graphes natifs | Moins documenté |
| **Tauri (Rust + JS)** | Léger, cross-platform, UI web | Complexité Rust pour HID |
| **Electron + node-hid** | Cross-platform, JS partout | Lourd |

**Recommandation** : Commencer avec Python (même stack que la Phase 1), migrer si besoin.

### Fonctionnalités requises

#### 2.1 Connexion

- Détecter automatiquement le pédalier au démarrage (scan VID/PID)
- Afficher statut de connexion
- Reconnecter automatiquement si déconnecté

#### 2.2 Visualisation temps réel

- Afficher la valeur brute de chaque pédale en direct (0–100%)
- Afficher la valeur après application de la courbe

#### 2.3 Éditeur de courbes

Pour chacune des 3 pédales (accélérateur, frein, embrayage) :
- Éditeur de courbe de réponse (interpolation cubique, comme l'originale)
- Minimum 5 points de contrôle éditables
- Affichage graphique de la courbe résultante
- Prévisualisation en temps réel

#### 2.4 Dead zones

- Dead zone basse (seuil d'activation)
- Dead zone haute (seuil de saturation)
- Réglage en % ou en valeur brute ADC

#### 2.5 Calibration

- Calibration min/max par pédale (appui complet + relâché)
- Stockage des valeurs de calibration

#### 2.6 Sauvegarde

- Envoyer et sauvegarder la configuration sur le pédalier
- Sauvegarder/charger des profils en local (JSON)
- Export/import de profils pour la communauté

#### 2.7 Firmware (Phase ultérieure)

- Flash firmware via drag & drop (reproduire la logique de `pitstop.venym.com/flash.php`)
- Logs de flash dans `C:\Users\Public\Documents\Venym\`

---

## Structure du projet

```
venym-pitstop-oss/
├── README.md
├── protocol.md          # Documentation du protocole USB (à remplir)
├── requirements.txt
├── src/
│   ├── usb/
│   │   ├── device.py    # Détection et connexion HID
│   │   ├── protocol.py  # Encodage/décodage des paquets
│   │   └── capture.py   # Outil de capture et analyse
│   ├── ui/
│   │   ├── main.py      # Fenêtre principale
│   │   ├── curve_editor.py
│   │   └── pedal_widget.py
│   └── core/
│       ├── config.py    # Modèle de configuration
│       └── profile.py   # Gestion des profils JSON
├── tools/
│   └── sniff.py         # Script standalone de capture USB
└── profiles/
    └── default.json
```

---

## Priorités de développement

1. **Script `tools/sniff.py`** — lire et afficher les données brutes USB du pédalier
2. **`src/usb/device.py`** — connexion HID stable avec reconnexion automatique
3. **`src/usb/protocol.py`** — à compléter au fur et à mesure du RE
4. **UI minimale** — affichage temps réel + éditeur de courbes
5. **Sauvegarde sur périphérique** — nécessite protocole complet
6. **Flash firmware** — phase finale

---

## Dépendances Python

```
hidapi>=0.14.0
pyusb>=1.2.1
customtkinter>=5.2.0   # ou dearpygui>=1.11.0
matplotlib>=3.8.0      # pour l'éditeur de courbes
numpy>=1.26.0
```

---

## Notes pour le reverse engineering

- Le pédalier expose probablement **2 interfaces HID** : une pour les axes (joystick standard), une vendor-defined pour la configuration
- L'interpolation est **cubique** (mentionné explicitement dans la doc Venym)
- Les valeurs sont probablement en **floating point** côté firmware (48 MHz MCU avec FPU probable)
- Chercher dans les descripteurs HID les `Usage Page` à `0xFF00` ou supérieur (vendor-defined)
- Les logs `FlashLog-*.txt` dans `C:\Users\Public\Documents\Venym` peuvent révéler des infos sur le protocole si un membre de la communauté les partage

---

## Ressources

- [hidapi Python](https://github.com/trezor/cython-hidapi)
- [pyusb](https://github.com/pyusb/pyusb)
- [USBPcap + Wireshark](https://desowin.org/usbpcap/) — capture USB Windows
- [USB HID Spec](https://www.usb.org/hid)
- Ancienne doc flash : `https://web.archive.org/web/*/pitstop.venym.com/*`
