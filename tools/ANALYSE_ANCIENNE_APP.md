# Analyse de l'ancienne app Venym PitStop

## Contexte

On a reverse-engineere le protocole USB du pedalier Venym Atrax (ATSAMD21E18A).
L'ancienne app contient probablement :
- La commande pour trigger le bootloader (flash firmware)
- Le protocole de flash complet
- Le vrai mapping des parametres
- Le HID descriptor attendu / driver virtuel

## Etapes a suivre sur un PC x64 Windows

### 1. Installer l'ancienne app

```
VenymSetup.1.10.3.exe
```

Installer normalement. Noter le dossier d'installation (probablement `C:\Program Files\Venym\` ou `C:\Users\<user>\AppData\Local\Venym\`).

### 2. Explorer les fichiers installes

L'app est probablement Electron (HTML/JS). Chercher :

```
dir /s /b "C:\Program Files\Venym\"
```

Ou si dans AppData :
```
dir /s /b "%LOCALAPPDATA%\Venym\"
```

Les fichiers interessants :
- `*.js` — code JavaScript (logique de l'app)
- `*.asar` — archive Electron (extractible avec `npx asar extract app.asar app_extracted`)
- `*.dll` — drivers ou libs natives
- `*.json` — config
- `*.html` — interface
- `resources/` — dossier Electron typique

### 3. Extraire le code source

Si c'est Electron, il y aura un fichier `app.asar` dans `resources/` :

```bash
npm install -g asar
asar extract "C:\Program Files\Venym\resources\app.asar" C:\temp\venym_src
```

Ou sans npm :
```bash
npx asar extract "C:\Program Files\Venym\resources\app.asar" C:\temp\venym_src
```

### 4. Chercher les infos critiques

Dans le code extrait, chercher :

```bash
# Commande bootloader / flash
grep -ri "boot" --include="*.js" .
grep -ri "dfu" --include="*.js" .
grep -ri "flash" --include="*.js" .
grep -ri "firmware" --include="*.js" .

# Protocole HID
grep -ri "feature" --include="*.js" .
grep -ri "report" --include="*.js" .
grep -ri "0x10\|0x11\|0x12" --include="*.js" .
grep -ri "send_feature\|getFeature\|setFeature" --include="*.js" .

# Dead zones et parametres
grep -ri "deadzone\|dead_zone" --include="*.js" .
grep -ri "force\|pressure\|calibr" --include="*.js" .
grep -ri "curve\|response" --include="*.js" .

# VID/PID et USB
grep -ri "3441\|1501\|03eb\|6124" --include="*.js" .
grep -ri "vendor\|product" --include="*.js" .

# vJoy ou driver virtuel
grep -ri "vjoy\|vigem\|virtual\|gamepad" --include="*.js" .
grep -ri "hid\|joystick" --include="*.js" .
```

### 5. Fichiers a copier pour analyse

Copier TOUT le dossier extrait et aussi :
- Les DLL dans le dossier d'installation
- Le dossier `resources/`
- Tout fichier `.bin`, `.hex`, `.uf2`, `.fw` (firmware)
- Les fichiers de log dans `C:\Users\Public\Documents\Venym\`

### 6. Ce qu'on cherche specifiquement

1. **Commande bootloader** : comment l'app trigger le mode flash
   - Probablement un Feature Report ou Output Report specifique
   - Ou un control transfer USB vendor-specific
   - Ou un reboot avec magic bytes

2. **Protocole de flash** : comment le firmware est ecrit
   - SAM-BA protocol ?
   - DFU standard ?
   - Protocole custom ?

3. **Driver virtuel** : comment l'app expose les axes aux jeux
   - vJoy integration ?
   - ViGEm ?
   - Driver HID custom ?
   - Ou pas de driver du tout (les jeux lisent le HID brut)

4. **HID descriptor** : est-ce que l'app modifie le descriptor
   - Ou est-ce que les jeux fonctionnent avec le descriptor 6x8bits actuel

5. **Mapping des parametres** :
   - Conversion exacte dead zone <-> param_a
   - Conversion exacte force <-> param_b
   - Encodage exact de la courbe (LUT firmware)
   - Signification du byte y2

## Hardware identifie

- **MCU** : Atmel ATSAMD21E18A-U (ARM Cortex-M0+ @ 48 MHz, 256 KB Flash, 32 KB RAM)
- **Connecteurs PCB** : J3, J4, J5 (2 pins chacun), J6 (mini-USB), J10
- **Bootloader ROM** : SAM-BA integre (Microchip)
- **Programmation** : SWD via connecteur J6 ou J3/J4/J5 (a identifier)

## VID/PID

- Normal : VID 0x3441, PID 0x1501
- Bootloader SAM-BA : probablement VID 0x03EB, PID 0x6124
- Firmware version : 1.13 (bcdDevice 0x010D)
