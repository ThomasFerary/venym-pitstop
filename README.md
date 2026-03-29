# Venym Pitstop — Open Source

Application open source de configuration pour les pedaliers SimRacing **Venym Atrax** (et potentiellement Black Widow).

Venym etait une marque francaise de pedaliers SimRacing qui a depose bilan. L'application officielle **Venym Pitstop** n'est plus disponible. Ce projet recrée une application de configuration complete basee sur le reverse engineering du protocole USB.

## Fonctionnalites

- Connexion automatique au pedalier (VID `0x3441` / PID `0x1501`)
- Lecture de la configuration stockee sur le pedalier au demarrage
- Visualisation temps reel des axes (accelerateur, frein, embrayage)
- Editeur de courbes de reponse (drag & drop des points de controle)
- Dead zone basse (firmware, par pas de 0.5%)
- Dead zone haute (firmware, via courbe)
- Reglage de la force/sensibilite du frein (load cell)
- Calibration min/max
- Sauvegarde/chargement de profils JSON
- Envoi de la configuration au pedalier (persistee en flash)

## Installation

### Prerequis

- Python 3.11+
- Windows 10/11 (le pedalier utilise le driver HID natif)
- Pedalier Venym Atrax branche en USB

### Setup

```bash
git clone https://github.com/votre-repo/venym-pitstop-oss.git
cd venym-pitstop-oss
pip install -r requirements.txt
```

### Lancement

```bash
python run.py
```

## Structure du projet

```
venym-pitstop-oss/
├── run.py                  # Point d'entree
├── requirements.txt        # Dependances Python
├── protocol.md             # Documentation complete du protocole USB
├── src/
│   ├── usb/
│   │   ├── device.py       # Connexion HID, reconnexion auto
│   │   ├── protocol.py     # Encodage/decodage Feature Reports, LUT courbe
│   │   └── capture.py      # Capture structuree pour analyse
│   ├── core/
│   │   ├── config.py       # Modele de configuration (courbes, calibration, dead zones)
│   │   └── profile.py      # Gestion des profils JSON
│   └── ui/
│       ├── main.py          # Fenetre principale CustomTkinter
│       ├── curve_editor.py  # Editeur de courbes interactif
│       └── pedal_widget.py  # Widget barre temps reel par pedale
├── tools/
│   ├── sniff.py            # Capture USB brute (enumeration + lecture HID)
│   ├── probe.py            # Exploration des Feature Reports
│   ├── backup.py           # Sauvegarde/restauration config pedalier
│   ├── restore_params.py   # Restauration rapide depuis backup.json
│   └── diag.py             # Diagnostic rapide des axes
└── profiles/
    └── default.json        # Profil par defaut
```

## Utilisation

### Premier lancement

1. Brancher le pedalier
2. Lancer `python run.py`
3. Cliquer **Connecter** — la configuration est lue automatiquement du pedalier
4. Les barres d'axes affichent les valeurs en temps reel (0-100%)

### Modifier la courbe

- Glisser les points de controle **verticalement** dans l'editeur de courbes
- La courbe est echantillonnee aux 5 positions firmware (20%, 40%, 60%, 80%, 100%)
- Le point (0%, 0%) est implicite
- Cliquer **Envoyer au pedalier** pour appliquer

### Dead zones

- **Dead zone basse** : pourcentage de course au repos ignore (boutons +/-, pas de 0.5%)
- **Dead zone haute** : pourcentage de course en butee ou la pedale atteint 100% (boutons +/-, pas de 0.5%)
- Les deux sont stockees dans le firmware et fonctionnent sans logiciel

### Force frein

- Controle la sensibilite du load cell (capteur de pression)
- Plus la valeur est haute, plus il faut appuyer fort
- Reglable par pas de 100 (boutons +/-)
- Ne s'applique qu'au frein (grise pour les autres pedales)

### Profils

- **Sauvegarder** : enregistre la configuration actuelle en JSON
- **Charger** : restaure une configuration sauvegardee
- Les profils sont dans le dossier `profiles/`

### Outils en ligne de commande

```bash
# Enumerer les peripheriques HID
python tools/sniff.py

# Capturer les donnees brutes
python tools/sniff.py --vid 0x3441 --pid 0x1501 --log capture.bin

# Sauvegarder la config du pedalier
python tools/backup.py --save backup.json

# Restaurer une config sauvegardee
python tools/backup.py --restore backup.json

# Diagnostic rapide des axes
python tools/diag.py
```

## Protocole USB

La documentation complete du protocole reverse engineere est dans [protocol.md](protocol.md).

Points cles :
- 1 interface HID, pas de Report ID (Feature Report unique de 63 bytes)
- Input Report 7B a ~500 Hz (axes post-traitement)
- Feature Reports 0x10/0x11/0x12 (38B chacun, config par pedale)
- Ecriture via `send_feature_report` avec double report_id (transport + selecteur)
- Configuration persistee en flash
- Courbe de reponse : 5 points avec LUT non-lineaire (plage utile y1=60-87)

## Limitations connues

- **Modele teste** : Atrax uniquement (2 pedales). Le Black Widow (3 pedales) n'a pas ete teste
- **Byte y2 (tangent)** : l'effet du 3eme byte de chaque point de courbe n'est pas entierement compris. Les valeurs originales sont preservees lors de l'envoi
- **Force frein** : la conversion param_b -> kg est approximative (~45.6 units/kg)
- **Courbe user** : la modification de la courbe dans l'editeur recalcule les y1 firmware via la LUT. De petites pertes de precision sont possibles du fait de la plage utile reduite (60-87)
- **Flash firmware** : le flash DFU n'est pas implemente

## Contribuer

Ce projet a ete cree pour la communaute SimRacing. Les contributions sont bienvenues :

- **Testeurs Black Widow** : si vous avez un Black Widow, vos Feature Reports nous aideraient a supporter ce modele
- **Logs ancienne app** : les fichiers `FlashLog-*.txt` dans `C:\Users\Public\Documents\Venym\` peuvent reveler des infos supplementaires
- **Byte y2** : des tests avec differentes valeurs de tangent pour comprendre l'interpolation cubique firmware
- **Interface** : ameliorations de l'UI (themes, responsive, etc.)

## Dependances

| Package         | Version | Usage                    |
|-----------------|---------|--------------------------|
| hidapi          | >=0.14  | Communication HID        |
| pyusb           | >=1.2   | Descripteurs USB         |
| libusb-package  | >=1.0   | Backend libusb Windows   |
| customtkinter   | >=5.2   | Interface graphique      |
| numpy           | >=1.26  | Calculs                  |
| scipy           | >=1.12  | Interpolation cubique    |
| matplotlib      | >=3.8   | (reserve pour l'avenir)  |

## Licence

Open source — a definir.
