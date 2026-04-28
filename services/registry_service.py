"""Persistência local de câmeras por UUID."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import CAMERA_REGISTRY_PATH

logger = logging.getLogger("RegistryService")


class RegistryService:
    """Serviço de inventário com persistência em arquivo JSON."""

    REQUIRED_FIELDS = {
        "uuid",
        "name",
        "streams",
        "has_visible",
        "has_visible_sub",
        "has_thermal",
        "has_thermal_sub",
        "stream_count",
        "enabled",
        "video_wall",
        "plugins",
        "node",
        "created_at",
    }

    def __init__(self, registry_path: str = CAMERA_REGISTRY_PATH) -> None:
        self.registry_path = Path(registry_path)
        self._registry: Dict[str, Dict[str, Any]] = {}
        self.load()

    def list_cameras(self) -> List[Dict[str, Any]]:
        return list(self._registry.values())

    def get_camera(self, uuid: str) -> Optional[Dict[str, Any]]:
        return self._registry.get(uuid)

    def add_camera(self, camera: Dict[str, Any]) -> Dict[str, Any]:
        camera = self._migrate_camera_model(camera)
        self._validate_minimum_fields(camera)
        camera_uuid = camera["uuid"]

        if camera_uuid in self._registry:
            raise ValueError(f"UUID duplicado: {camera_uuid}")

        self._registry[camera_uuid] = camera
        self.save()
        logger.info("Câmera adicionada ao registro: uuid=%s", camera_uuid)
        return camera

    def remove_camera(self, uuid: str) -> bool:
        if uuid not in self._registry:
            return False

        del self._registry[uuid]
        self.save()
        logger.info("Câmera removida do registro: uuid=%s", uuid)
        return True

    def load(self) -> Dict[str, Dict[str, Any]]:
        if not self.registry_path.exists():
            self._registry = {}
            logger.info("Arquivo de registro inexistente. Iniciando inventário vazio: %s", self.registry_path)
            return self._registry

        try:
            with self.registry_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except json.JSONDecodeError:
            corrupt_path = self.registry_path.with_suffix(self.registry_path.suffix + ".corrupt")
            self.registry_path.rename(corrupt_path)
            self._registry = {}
            logger.error(
                "JSON corrompido detectado em %s. Backup em %s e inventário reiniciado vazio.",
                self.registry_path,
                corrupt_path,
            )
            return self._registry
        except OSError as exc:
            self._registry = {}
            logger.error("Erro de I/O ao carregar registro %s: %s. Iniciando vazio.", self.registry_path, exc)
            return self._registry

        if not isinstance(data, dict):
            logger.warning("Formato inválido de registro em %s (esperado objeto). Reiniciando vazio.", self.registry_path)
            self._registry = {}
            return self._registry

        migrated_registry: Dict[str, Dict[str, Any]] = {}
        for key, value in data.items():
            if not isinstance(value, dict):
                continue
            migrated = self._migrate_camera_model(value)
            migrated_registry[str(key)] = migrated

        self._registry = migrated_registry
        self.save()
        logger.info("Registro carregado: %s câmera(s)", len(self._registry))
        return self._registry

    def save(self) -> None:
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with self.registry_path.open("w", encoding="utf-8") as fp:
                json.dump(self._registry, fp, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("Erro de I/O ao salvar registro %s: %s", self.registry_path, exc)
            raise

    def _validate_minimum_fields(self, camera: Dict[str, Any]) -> None:
        missing = [field for field in self.REQUIRED_FIELDS if field not in camera]
        if missing:
            raise ValueError(f"Campos obrigatórios ausentes: {', '.join(sorted(missing))}")

        if not isinstance(camera.get("plugins"), list):
            raise ValueError("Campo 'plugins' deve ser uma lista")

        if not isinstance(camera.get("streams"), dict):
            raise ValueError("Campo 'streams' deve ser um objeto")

    def _migrate_camera_model(self, camera: Dict[str, Any]) -> Dict[str, Any]:
        migrated = dict(camera)

        streams = migrated.get("streams")
        if not isinstance(streams, dict):
            stream_name = migrated.get("stream_name")
            source_url = migrated.get("source_url", "")
            streams = {
                "visible": {
                    "main": {
                        "stream_name": stream_name,
                        "source_url": source_url,
                    },
                    "sub": None,
                },
                "thermal": {
                    "main": None,
                    "sub": None,
                },
            }
        else:
            streams.setdefault("visible", {"main": None, "sub": None})
            streams.setdefault("thermal", {"main": None, "sub": None})
            streams["visible"].setdefault("main", None)
            streams["visible"].setdefault("sub", None)
            streams["thermal"].setdefault("main", None)
            streams["thermal"].setdefault("sub", None)

        migrated["streams"] = streams

        visible_main = streams.get("visible", {}).get("main")
        visible_sub = streams.get("visible", {}).get("sub")
        thermal_main = streams.get("thermal", {}).get("main")
        thermal_sub = streams.get("thermal", {}).get("sub")

        migrated["has_visible"] = bool(visible_main and visible_main.get("stream_name"))
        migrated["has_visible_sub"] = bool(visible_sub and visible_sub.get("stream_name"))
        migrated["has_thermal"] = bool(thermal_main and thermal_main.get("stream_name"))
        migrated["has_thermal_sub"] = bool(thermal_sub and thermal_sub.get("stream_name"))
        migrated["stream_count"] = sum(
            [migrated["has_visible"], migrated["has_visible_sub"], migrated["has_thermal"], migrated["has_thermal_sub"]]
        )

        if visible_main:
            migrated["stream_name"] = visible_main.get("stream_name")
            migrated["source_url"] = visible_main.get("source_url", "")
        else:
            migrated.setdefault("stream_name", None)
            migrated.setdefault("source_url", "")

        migrated.setdefault("enabled", True)
        migrated.setdefault("video_wall", False)
        plugins = migrated.get("plugins") if isinstance(migrated.get("plugins"), list) else []
        migrated["plugins"] = [p for p in plugins if str(p).strip().lower() != "yolo"]
        migrated.setdefault("node", "auto")
        migrated.setdefault("created_at", "")

        return migrated
