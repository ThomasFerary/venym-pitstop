"""
Venym Pedals — Profile Manager

Gestion des profils de configuration (sauvegarde/chargement JSON).
"""

import json
from pathlib import Path
from datetime import datetime

from .config import FullConfig


PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"


class ProfileManager:
    """Gère les profils de configuration JSON."""

    def __init__(self, profiles_dir: Path | None = None):
        self.profiles_dir = profiles_dir or PROFILES_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        """Liste les noms de profils disponibles (sans extension)."""
        return sorted(
            p.stem for p in self.profiles_dir.glob("*.json")
        )

    def save(self, name: str, config: FullConfig, description: str = ""):
        """Sauvegarde un profil JSON."""
        data = {
            "name": name,
            "description": description,
            "created": datetime.now().isoformat(),
            "version": 1,
            "config": config.to_dict(),
        }
        path = self.profiles_dir / f"{name}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, name: str) -> FullConfig:
        """Charge un profil JSON et retourne la config."""
        path = self.profiles_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Profil introuvable : {name}")

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return FullConfig.from_dict(data["config"])

    def delete(self, name: str):
        """Supprime un profil."""
        path = self.profiles_dir / f"{name}.json"
        if path.exists():
            path.unlink()

    def export_profile(self, name: str, dest: Path):
        """Exporte un profil vers un chemin arbitraire (partage communauté)."""
        src = self.profiles_dir / f"{name}.json"
        if not src.exists():
            raise FileNotFoundError(f"Profil introuvable : {name}")
        dest.write_bytes(src.read_bytes())

    def import_profile(self, src: Path, name: str | None = None):
        """Importe un profil depuis un fichier externe."""
        with src.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Validation minimale
        if "config" not in data:
            raise ValueError("Fichier de profil invalide (clé 'config' manquante)")

        # Utiliser le nom du fichier si pas spécifié
        if name is None:
            name = data.get("name", src.stem)

        dest = self.profiles_dir / f"{name}.json"
        with dest.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
