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
        "source_type",
        "source_url",
        "stream_name",
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
        self._validate_minimum_fields(camera)
        camera_uuid = camera["uuid"]

        if camera_uuid in self._registry:
            raise ValueError(f"UUID duplicado: {camera_uuid}")

        self._registry[camera_uuid] = camera
        self.save()
        logger.info("Câmera adicionada ao registro: uuid=%s stream=%s", camera_uuid, camera.get("stream_name"))
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

        self._registry = {str(key): value for key, value in data.items() if isinstance(value, dict)}
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
