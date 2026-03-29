# Venym PitStop Open Source

> Ce projet n'est pas affilie a Venym. Venym est une marque deposee de ses proprietaires respectifs.
>
> This project is not affiliated with Venym. Venym is a trademark of its respective owners.

---

**[Francais](#francais)** | **[English](#english)**

---

## Francais

Application open source de remplacement pour le logiciel de configuration Venym PitStop. Creee pour la communaute SimRacing apres la fermeture de Venym et la disparition de l'application officielle.

Le protocole USB HID a ete entierement reverse-engineere. Tous les reglages sont ecrits directement dans le firmware du pedalier et fonctionnent sans l'application.

### Materiel supporte

- **Venym Atrax** (2 pedales : accelerateur + frein) — entierement teste
- **Venym Black Widow** (3 pedales) — non teste, contributions bienvenues

### Telecharger

Recuperez le dernier **VenymPitStop.exe** depuis la page [Releases](https://github.com/ThomasFerary/venym-pitstop/releases). Aucune installation requise — il suffit de le lancer.

Ou lancer depuis les sources :
```bash
git clone https://github.com/ThomasFerary/venym-pitstop.git
cd venym-pitstop
pip install -r requirements.txt
python run.py
```

Necessite Python 3.11+ et Windows 10/11.

### Fonctionnalites

- **Visualisation temps reel** des pedales avec barres de progression
- **Editeur de courbes** — deplacez les points de controle pour modifier la reponse, stockee dans le firmware
- **Dead zones** — basse et haute, ajustables par pas de 0.5%
- **Force de freinage** — reglage de la pression maximale en kg (load cell)
- **Calibration** — calibration min/max basee sur le firmware
- **Profils** — sauvegarde/chargement de configurations en JSON
- **Backup/Restauration** — export et import des reglages bruts du pedalier
- **Compteur horaire** — affiche le temps d'utilisation total depuis le firmware
- **Bilingue** — interface en francais et anglais

Tous les reglages sont persistants dans la memoire flash du pedalier. Le pedalier fonctionne de facon autonome — l'application n'est necessaire que pour modifier la configuration.

### Utilisation

1. Branchez vos pedales
2. Cliquez **Connecter**
3. Ajustez les courbes, dead zones et force de freinage
4. Cliquez **Envoyer au pedalier** pour appliquer
5. Utilisez **Calibrer tout** pour definir la plage min/max (appuyez et relachez chaque pedale, puis cliquez a nouveau)

### Sauvegardez vos reglages

Avant de modifier quoi que ce soit, utilisez **Exporter backup** pour sauvegarder votre configuration actuelle dans un fichier JSON. En cas de probleme, utilisez **Importer backup** pour la restaurer.

> **Important :** Ce logiciel a ete construit par reverse engineering. Bien qu'il ait ete teste de maniere approfondie, exportez toujours un backup avant de modifier les reglages de votre pedalier.

### Limitations connues

- **Atrax uniquement** — le support du Black Widow necessite des tests de la communaute
- **Precision des courbes** — le firmware utilise une LUT non-lineaire avec une plage utile reduite. De legers ecarts d'arrondi sont possibles
- **Flash firmware** — le mode DFU n'est pas implemente
- **Normalisation de l'affichage** — le pourcentage affiche depend de la qualite de la calibration. Recalibrez apres avoir modifie les dead zones

### Contribuer

- **Proprietaires de Black Widow** — partagez vos dumps de Feature Reports pour ajouter le support
- **Utilisateurs de l'ancienne app** — les fichiers FlashLog dans `C:\Users\Public\Documents\Venym\` peuvent contenir des infos utiles
- **Ameliorations de l'UI** — l'app utilise CustomTkinter, les PRs sont bienvenues

---

## English

Open source replacement for the Venym PitStop configuration software. Built for the SimRacing community after Venym went out of business and the official app became unavailable.

The USB HID protocol has been fully reverse-engineered. All settings are written directly to the pedal firmware and work without the app running.

### Supported Hardware

- **Venym Atrax** (2 pedals: throttle + brake) -- fully tested
- **Venym Black Widow** (3 pedals) -- untested, contributions welcome

### Download

Grab the latest **VenymPitStop.exe** from the [Releases](https://github.com/ThomasFerary/venym-pitstop/releases) page. No installation required -- just run it.

Or run from source:
```bash
git clone https://github.com/ThomasFerary/venym-pitstop.git
cd venym-pitstop
pip install -r requirements.txt
python run.py
```

Requires Python 3.11+ and Windows 10/11.

### Features

- **Real-time pedal visualization** with per-pedal progress bars
- **Response curve editor** -- drag control points to shape the pedal response, stored in firmware
- **Dead zones** -- lower and upper, adjustable in 0.5% steps
- **Brake force** -- max pressure setting in kg (load cell)
- **Calibration** -- firmware-based min/max calibration
- **Profiles** -- save/load configurations as JSON files
- **Backup/Restore** -- export and import raw pedal settings to protect against accidental changes
- **Time meter** -- displays total usage hours from firmware
- **Bilingual** -- French and English interface

All settings are persisted in the pedal's flash memory. The pedal works standalone -- the app is only needed to change configuration.

### Usage

1. Plug in your pedals
2. Click **Connect**
3. Adjust curves, dead zones, and brake force
4. Click **Send to pedal** to apply
5. Use **Calibrate all** to set min/max range (press and release each pedal, then click again)

### Backup your settings

Before making changes, use **Export backup** to save your current pedal configuration to a JSON file. If anything goes wrong, use **Import backup** to restore it.

> **Important:** This software was built through reverse engineering. While it has been tested extensively, always export a backup before modifying your pedal settings.

### Known Limitations

- **Atrax only** -- Black Widow support needs testing from the community
- **Curve precision** -- the firmware uses a non-linear LUT with a narrow useful range. Small rounding differences are possible
- **Firmware flash** -- DFU mode is not implemented
- **Display normalization** -- the percentage shown depends on calibration quality. Recalibrate after changing dead zones

### Contributing

- **Black Widow owners** -- share your Feature Report dumps so we can add support
- **Old app users** -- if you have FlashLog files from `C:\Users\Public\Documents\Venym\`, they may contain useful protocol info
- **UI improvements** -- the app uses CustomTkinter, PRs for better layouts or features are welcome

---

## Protocol Documentation

The full reverse-engineered USB HID protocol is documented in [protocol.md](protocol.md).

## License

[MIT](LICENSE)
