"""
Venym Pedals — HID Device Management

Gère la détection, connexion et reconnexion automatique au pédalier.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import hid


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class DeviceInfo:
    """Informations sur un périphérique HID Venym détecté."""
    vendor_id: int
    product_id: int
    product_string: str
    manufacturer_string: str
    path: bytes
    interface_number: int
    usage_page: int
    usage: int

    @property
    def is_vendor_defined(self) -> bool:
        return self.usage_page >= 0xFF00

    @property
    def vid_pid_str(self) -> str:
        return f"0x{self.vendor_id:04x}:0x{self.product_id:04x}"


class VenymDevice:
    """
    Gère la connexion HID au pédalier Venym.

    Expose deux interfaces :
    - Interface axes (joystick HID standard) : lecture des valeurs pédales
    - Interface config (vendor-defined) : lecture/écriture de la configuration

    Supporte la reconnexion automatique en arrière-plan.
    """

    # VID/PID connus — à remplir après identification
    KNOWN_VIDS_PIDS: list[tuple[int, int]] = [
        (0x3441, 0x1501),  # Atrax
    ]

    def __init__(self):
        self._device_axes: hid.device | None = None
        self._device_config: hid.device | None = None
        self._state = ConnectionState.DISCONNECTED
        self._info: DeviceInfo | None = None
        self._lock = threading.Lock()

        # Callbacks
        self._on_state_change: Callable[[ConnectionState], None] | None = None
        self._on_data: Callable[[list[int]], None] | None = None

        # Reconnexion auto
        self._reconnect_thread: threading.Thread | None = None
        self._reconnect_stop = threading.Event()

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def info(self) -> DeviceInfo | None:
        return self._info

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def on_state_change(self, callback: Callable[[ConnectionState], None]):
        self._on_state_change = callback

    def on_data(self, callback: Callable[[list[int]], None]):
        self._on_data = callback

    def _set_state(self, state: ConnectionState):
        self._state = state
        if self._on_state_change:
            self._on_state_change(state)

    @staticmethod
    def scan() -> list[DeviceInfo]:
        """Scanne tous les périphériques HID et retourne ceux qui pourraient être des Venym."""
        results = []
        for dev in hid.enumerate():
            results.append(DeviceInfo(
                vendor_id=dev["vendor_id"],
                product_id=dev["product_id"],
                product_string=dev.get("product_string") or "",
                manufacturer_string=dev.get("manufacturer_string") or "",
                path=dev["path"],
                interface_number=dev.get("interface_number", -1),
                usage_page=dev.get("usage_page", 0),
                usage=dev.get("usage", 0),
            ))
        return results

    @staticmethod
    def find_venym_devices() -> list[DeviceInfo]:
        """Cherche spécifiquement les pédaliers Venym (par VID/PID ou nom)."""
        devices = VenymDevice.scan()
        venym = []
        for d in devices:
            # Chercher par VID/PID connus
            if (d.vendor_id, d.product_id) in VenymDevice.KNOWN_VIDS_PIDS:
                venym.append(d)
                continue
            # Chercher par nom
            name = f"{d.manufacturer_string} {d.product_string}".lower()
            if "venym" in name or "atrax" in name or "black widow" in name:
                venym.append(d)
        return venym

    def connect(self, vid: int, pid: int) -> bool:
        """
        Connecte au pédalier par VID/PID.
        Ouvre l'interface axes et, si disponible, l'interface config (vendor-defined).
        """
        with self._lock:
            self._set_state(ConnectionState.CONNECTING)

            # Trouver les interfaces disponibles pour ce VID/PID
            interfaces = [d for d in self.scan()
                          if d.vendor_id == vid and d.product_id == pid]

            if not interfaces:
                self._set_state(ConnectionState.ERROR)
                return False

            try:
                # Ouvrir l'interface axes (non vendor-defined, typiquement usage_page 0x01)
                axes_ifaces = [d for d in interfaces if not d.is_vendor_defined]
                if axes_ifaces:
                    self._device_axes = hid.device()
                    self._device_axes.open_path(axes_ifaces[0].path)
                    self._device_axes.set_nonblocking(1)
                    self._info = axes_ifaces[0]

                # Ouvrir l'interface config (vendor-defined)
                config_ifaces = [d for d in interfaces if d.is_vendor_defined]
                if config_ifaces:
                    self._device_config = hid.device()
                    self._device_config.open_path(config_ifaces[0].path)
                    self._device_config.set_nonblocking(1)
                    if self._info is None:
                        self._info = config_ifaces[0]

                if self._device_axes is None and self._device_config is None:
                    self._set_state(ConnectionState.ERROR)
                    return False

                self._set_state(ConnectionState.CONNECTED)
                return True

            except OSError:
                self._set_state(ConnectionState.ERROR)
                return False

    def connect_path(self, path: bytes) -> bool:
        """Connecte directement via le path HID."""
        with self._lock:
            self._set_state(ConnectionState.CONNECTING)
            try:
                self._device_axes = hid.device()
                self._device_axes.open_path(path)
                self._device_axes.set_nonblocking(1)
                self._set_state(ConnectionState.CONNECTED)
                return True
            except OSError:
                self._set_state(ConnectionState.ERROR)
                return False

    def disconnect(self):
        """Déconnecte proprement."""
        with self._lock:
            self.stop_auto_reconnect()
            if self._device_axes:
                self._device_axes.close()
                self._device_axes = None
            if self._device_config:
                self._device_config.close()
                self._device_config = None
            self._info = None
            self._set_state(ConnectionState.DISCONNECTED)

    def read_axes(self) -> list[int] | None:
        """Lit un paquet de données brutes depuis l'interface axes."""
        if not self._device_axes:
            return None
        try:
            data = self._device_axes.read(64)
            return data if data else None
        except OSError:
            self._set_state(ConnectionState.ERROR)
            return None

    def get_feature_report(self, report_id: int, size: int = 64) -> list[int] | None:
        """Lit un Feature Report depuis le device (axes interface)."""
        if not self._device_axes:
            return None
        try:
            return self._device_axes.get_feature_report(report_id, size)
        except OSError:
            return None

    def send_feature_report(self, data: bytes) -> bool:
        """Envoie un Feature Report (Set Feature Report) sur le device."""
        if not self._device_axes:
            return False
        try:
            self._device_axes.send_feature_report(data)
            return True
        except OSError:
            return False

    def read_config(self) -> list[int] | None:
        """Lit un paquet depuis l'interface config (vendor-defined)."""
        if not self._device_config:
            return None
        try:
            data = self._device_config.read(64)
            return data if data else None
        except OSError:
            return None

    def write_config(self, data: bytes) -> bool:
        """Envoie un paquet sur l'interface config."""
        if not self._device_config:
            return False
        try:
            self._device_config.write(data)
            return True
        except OSError:
            return False

    def start_auto_reconnect(self, vid: int, pid: int, interval: float = 2.0):
        """Lance un thread de reconnexion automatique."""
        self._reconnect_stop.clear()

        def _reconnect_loop():
            while not self._reconnect_stop.is_set():
                if self._state != ConnectionState.CONNECTED:
                    self.connect(vid, pid)
                self._reconnect_stop.wait(interval)

        self._reconnect_thread = threading.Thread(
            target=_reconnect_loop, daemon=True, name="venym-reconnect"
        )
        self._reconnect_thread.start()

    def stop_auto_reconnect(self):
        """Stoppe le thread de reconnexion."""
        self._reconnect_stop.set()
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=3)
            self._reconnect_thread = None
