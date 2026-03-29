"""
Venym PitStop — Internationalization
"""

TRANSLATIONS = {
    "fr": {
        "app_title": "Venym PitStop",
        "no_device": "Aucun pedalier connecte",
        "disconnected": "Deconnecte",
        "connecting": "Connexion...",
        "error": "Erreur",
        "no_device_found": "Aucun pedalier trouve",
        "connect_failed": "Echec connexion",
        "not_connected": "Non connecte",
        "connect": "Connecter",
        "send": "Envoyer au pedalier",
        "config_sent": "Config envoyee ({n} pedales)",
        "time_meter": "Temps d'utilisation : {h}h {m:02d}m",
        "profile": "Profil",
        "load": "Charger",
        "save": "Sauvegarder",
        "calibrate_all": "Calibrer tout",
        "calibrating": "Appuie a fond puis relache chaque pedale. Re-clique pour terminer.",
        "calibration_done": "Calibration sauvegardee",
        "profile_loaded": "Profil '{name}' charge",
        "profile_saved": "Profil '{name}' sauvegarde",
        "profile_not_found": "Profil introuvable",
        "export_backup": "Exporter backup",
        "import_backup": "Importer backup",
        "backup_exported": "Backup exporte",
        "backup_restored": "Backup restaure ({n} pedales)",
        "backup_invalid": "Format de backup invalide",
        "file_invalid": "Fichier invalide",
        "restore_confirm_title": "Restaurer la configuration",
        "restore_confirm_msg": "Cela va ecraser la configuration actuelle du pedalier.\n\nBackup: {device} ({time})\n\nContinuer ?",
        "export_dialog_title": "Exporter la configuration du pedalier",
        "import_dialog_title": "Importer une configuration pedalier",
        "clutch": "Embrayage",
        "brake": "Frein",
        "throttle": "Accelerateur",
        "dz_low": "Deadzone basse",
        "dz_high": "Deadzone haute",
        "force": "Force maximale",
    },
    "en": {
        "app_title": "Venym PitStop",
        "no_device": "No pedal connected",
        "disconnected": "Disconnected",
        "connecting": "Connecting...",
        "error": "Error",
        "no_device_found": "No pedal found",
        "connect_failed": "Connection failed",
        "not_connected": "Not connected",
        "connect": "Connect",
        "send": "Send to pedal",
        "config_sent": "Config sent ({n} pedals)",
        "time_meter": "Usage time: {h}h {m:02d}m",
        "profile": "Profile",
        "load": "Load",
        "save": "Save",
        "calibrate_all": "Calibrate all",
        "calibrating": "Press each pedal to max then release. Click again to finish.",
        "calibration_done": "Calibration saved",
        "profile_loaded": "Profile '{name}' loaded",
        "profile_saved": "Profile '{name}' saved",
        "profile_not_found": "Profile not found",
        "export_backup": "Export backup",
        "import_backup": "Import backup",
        "backup_exported": "Backup exported",
        "backup_restored": "Backup restored ({n} pedals)",
        "backup_invalid": "Invalid backup format",
        "file_invalid": "Invalid file",
        "restore_confirm_title": "Restore configuration",
        "restore_confirm_msg": "This will overwrite the current pedal configuration.\n\nBackup: {device} ({time})\n\nContinue?",
        "export_dialog_title": "Export pedal configuration",
        "import_dialog_title": "Import pedal configuration",
        "clutch": "Clutch",
        "brake": "Brake",
        "throttle": "Throttle",
        "dz_low": "Lower deadzone",
        "dz_high": "Upper deadzone",
        "force": "Max force",
    },
}

_current_lang = "fr"


def set_lang(lang: str):
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_lang() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    """Get translated string. Use kwargs for formatting."""
    text = TRANSLATIONS.get(_current_lang, TRANSLATIONS["fr"]).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
