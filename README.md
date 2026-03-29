# Venym PitStop Open Source

> This project is not affiliated with Venym. Venym is a trademark of its respective owners.

Open source replacement for the Venym PitStop configuration software. Built for the SimRacing community after Venym went out of business and the official app became unavailable.

The USB HID protocol has been fully reverse-engineered. All settings are written directly to the pedal firmware and work without the app running.

## Supported Hardware

- **Venym Atrax** (2 pedals: throttle + brake) -- fully tested
- **Venym Black Widow** (3 pedals) -- untested, contributions welcome

## Download

Grab the latest **VenymPitStop.exe** from the [Releases](https://github.com/ThomasFerary/venym-pitstop/releases) page. No installation required -- just run it.

Or run from source:
```bash
git clone https://github.com/ThomasFerary/venym-pitstop.git
cd venym-pitstop
pip install -r requirements.txt
python run.py
```

Requires Python 3.11+ and Windows 10/11.

## Features

- **Real-time pedal visualization** with per-pedal progress bars
- **Response curve editor** -- drag control points to shape the pedal response, stored in firmware
- **Dead zones** -- lower and upper, adjustable in 0.5% steps
- **Brake force** -- max pressure setting in kg (load cell)
- **Calibration** -- firmware-based min/max calibration
- **Profiles** -- save/load configurations as JSON files
- **Backup/Restore** -- export and import raw pedal settings to protect against accidental changes
- **Time meter** -- displays total usage hours from firmware

All settings are persisted in the pedal's flash memory. The pedal works standalone -- the app is only needed to change configuration.

## Usage

1. Plug in your pedals
2. Click **Connect**
3. Adjust curves, dead zones, and brake force
4. Click **Send to pedal** to apply
5. Use **Calibrate all** to set min/max range (press and release each pedal, then click again)

### Backup your settings

Before making changes, use **Export backup** to save your current pedal configuration to a JSON file. If anything goes wrong, use **Import backup** to restore it.

> **Important:** This software was built through reverse engineering. While it has been tested extensively, always export a backup before modifying your pedal settings.

## Protocol Documentation

The full reverse-engineered USB HID protocol is documented in [protocol.md](protocol.md), including:

- Input Report structure (7 bytes, axes at ~500 Hz)
- Feature Reports 0x10/0x11/0x12 (38 bytes per pedal, read/write)
- Curve encoding with firmware LUT
- Dead zone and brake force parameters
- Write protocol (double report ID, 64-byte payload)
- Time meter decoding

## Known Limitations

- **Atrax only** -- Black Widow support needs testing from the community
- **Curve precision** -- the firmware uses a non-linear LUT with a narrow useful range (y1=60-87). Small rounding differences are possible
- **Firmware flash** -- DFU mode is not implemented
- **Display normalization** -- the percentage shown depends on calibration quality. Recalibrate after changing dead zones

## Contributing

This project exists for the SimRacing community. Contributions are welcome:

- **Black Widow owners** -- share your Feature Report dumps so we can add support
- **Old app users** -- if you have FlashLog files from `C:\Users\Public\Documents\Venym\`, they may contain useful protocol info
- **UI improvements** -- the app uses CustomTkinter, PRs for better layouts or features are welcome

## License

[MIT](LICENSE)
