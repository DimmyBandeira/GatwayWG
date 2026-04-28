from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = "onvif_bridge/onvif_bridge_config.json"


@dataclass(frozen=True)
class BridgeDevice:
    virtual_ip: str
    camera_uuid: str
    name: str
    manufacturer: str
    model: str
    profile_token: str


@dataclass(frozen=True)
class BridgeConfig:
    gateway_ip: str
    rtsp_port: int
    http_port: int
    auth_user: str
    auth_pass: str
    auth_mode: str
    devices: list[BridgeDevice]

    def get_device_by_virtual_ip(self, virtual_ip: str) -> BridgeDevice | None:
        needle = (virtual_ip or "").strip()
        for device in self.devices:
            if device.virtual_ip == needle:
                return device
        return None

    def sanitized_devices(self) -> list[dict[str, str]]:
        return [
            {
                "virtual_ip": d.virtual_ip,
                "camera_uuid": d.camera_uuid,
                "name": d.name,
                "manufacturer": d.manufacturer,
                "model": d.model,
                "profile_token": d.profile_token,
            }
            for d in self.devices
        ]


class BridgeConfigError(ValueError):
    pass


def _require_str(item: dict[str, Any], key: str, where: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BridgeConfigError(f"Campo obrigatório inválido: {where}.{key}")
    return value.strip()


def _require_int(item: dict[str, Any], key: str, where: str) -> int:
    value = item.get(key)
    if not isinstance(value, int):
        raise BridgeConfigError(f"Campo obrigatório inválido: {where}.{key}")
    return value


def load_config(config_path: str | None = None) -> BridgeConfig:
    path = config_path or os.getenv("ONVIF_BRIDGE_CONFIG", DEFAULT_CONFIG_PATH)
    file_path = Path(path)
    if not file_path.exists():
        raise BridgeConfigError(f"Arquivo de configuração não encontrado: {file_path}")

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BridgeConfigError(f"JSON inválido em {file_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BridgeConfigError("Configuração inválida: raiz deve ser objeto JSON")

    gateway_ip = _require_str(payload, "gateway_ip", "root")
    rtsp_port = _require_int(payload, "rtsp_port", "root")
    http_port = _require_int(payload, "http_port", "root")
    auth_user = _require_str(payload, "auth_user", "root")
    auth_pass = _require_str(payload, "auth_pass", "root")
    auth_mode = str(payload.get("auth_mode", "basic")).strip().lower()
    if auth_mode not in {"basic", "none"}:
        raise BridgeConfigError("Campo inválido: root.auth_mode (use 'basic' ou 'none')")

    raw_devices = payload.get("devices")
    if not isinstance(raw_devices, list) or not raw_devices:
        raise BridgeConfigError("Campo obrigatório inválido: root.devices")

    devices: list[BridgeDevice] = []
    for idx, item in enumerate(raw_devices):
        if not isinstance(item, dict):
            raise BridgeConfigError(f"Dispositivo inválido em root.devices[{idx}]")
        devices.append(
            BridgeDevice(
                virtual_ip=_require_str(item, "virtual_ip", f"root.devices[{idx}]"),
                camera_uuid=_require_str(item, "camera_uuid", f"root.devices[{idx}]"),
                name=_require_str(item, "name", f"root.devices[{idx}]"),
                manufacturer=_require_str(item, "manufacturer", f"root.devices[{idx}]"),
                model=_require_str(item, "model", f"root.devices[{idx}]"),
                profile_token=_require_str(item, "profile_token", f"root.devices[{idx}]"),
            )
        )

    return BridgeConfig(
        gateway_ip=gateway_ip,
        rtsp_port=rtsp_port,
        http_port=http_port,
        auth_user=auth_user,
        auth_pass=auth_pass,
        auth_mode=auth_mode,
        devices=devices,
    )
