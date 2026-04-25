from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from integrations.go2rtc_client import Go2RTCClient
from services.capture_engine import CaptureEngine
from services.registry_service import RegistryService

logger = logging.getLogger("GatewayApp")

app = FastAPI(title="WebGuardião Gateway Master", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registry_service = RegistryService()
go2rtc_client = Go2RTCClient()
active_engines: Dict[str, CaptureEngine] = {}


class CameraPayload(BaseModel):
    uuid: str
    name: str
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    stream_name: Optional[str] = None
    enabled: Optional[bool] = True
    video_wall: Optional[bool] = False
    plugins: Optional[List[str]] = None
    node: Optional[str] = "auto"
    created_at: Optional[str] = None

    # Compatibilidade com contrato antigo
    type: Optional[str] = None
    path: Optional[str] = None
    videoWall: Optional[bool] = None
    createdAt: Optional[str] = None
    pipeline: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_camera(payload: CameraPayload) -> Dict[str, Any]:
    source_type = payload.source_type or payload.type
    source_url = payload.source_url or payload.path
    if not source_type or source_url is None:
        raise ValueError("Campos obrigatórios ausentes: source_type/source_url")

    created_at = payload.created_at or payload.createdAt or _utc_now_iso()
    video_wall = payload.video_wall if payload.video_wall is not None else bool(payload.videoWall)
    stream_name = payload.stream_name or payload.uuid

    return {
        "uuid": payload.uuid,
        "name": payload.name,
        "source_type": source_type,
        "source_url": source_url,
        "stream_name": stream_name,
        "enabled": bool(payload.enabled) if payload.enabled is not None else True,
        "video_wall": bool(video_wall),
        "plugins": payload.plugins or [],
        "node": payload.node or "auto",
        "created_at": created_at,
    }


def _resolve_sync_sets(
    cameras: List[Dict[str, Any]],
    go2rtc_online: bool,
    streams_index: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not go2rtc_online:
        for camera in cameras:
            logger.info("camera_missing_in_go2rtc uuid=%s stream=%s", camera.get("uuid"), camera.get("stream_name"))
        return [], cameras, []

    stream_names = set(streams_index.keys())
    matched = [camera for camera in cameras if (camera.get("stream_name") in stream_names)]
    missing_in_go2rtc = [camera for camera in cameras if (camera.get("stream_name") not in stream_names)]
    for camera in missing_in_go2rtc:
        logger.info("camera_missing_in_go2rtc uuid=%s stream=%s", camera.get("uuid"), camera.get("stream_name"))

    registry_stream_names = {camera.get("stream_name") for camera in cameras}
    not_imported = [
        {"stream_name": stream_name, **(streams_index.get(stream_name) or {})}
        for stream_name in stream_names
        if stream_name not in registry_stream_names
    ]
    return matched, missing_in_go2rtc, not_imported


def _enrich_camera(
    camera: Dict[str, Any],
    go2rtc_online: bool,
    streams_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    stream_name = camera.get("stream_name") or camera.get("uuid")
    urls = go2rtc_client.build_stream_urls(stream_name)
    streams_index = streams_index or {}

    go2rtc_registered = bool(go2rtc_online and stream_name in streams_index)
    if not go2rtc_online:
        status_label = "go2rtc_offline"
    elif go2rtc_registered:
        status_label = "online"
    else:
        status_label = "not_published"

    payload = dict(camera)
    payload["urls"] = urls
    payload["go2rtc_registered"] = go2rtc_registered
    payload["status_label"] = status_label
    payload["go2rtc"] = {
        "registered": go2rtc_registered,
        "status": status_label,
    }
    return payload


@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("cadastro.html")


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "online", "version": "2.0.0"}


@app.get("/go2rtc/health")
def go2rtc_health() -> Dict[str, Any]:
    return go2rtc_client.healthcheck()


@app.get("/go2rtc/streams")
def go2rtc_streams() -> List[Dict[str, Any]]:
    return go2rtc_client.get_active_streams()


@app.get("/sync/status")
def sync_status() -> Dict[str, Any]:
    logger.info("sync_status_requested")
    registered_cameras = registry_service.list_cameras()
    snapshot = go2rtc_client.get_streams_snapshot()
    go2rtc_online = bool(snapshot["online"])
    streams_index = snapshot["streams"]

    if go2rtc_online:
        go2rtc_streams = [
            {"stream_name": stream_name, **(details or {})}
            for stream_name, details in streams_index.items()
        ]
    else:
        go2rtc_streams = []

    matched, missing_in_go2rtc, not_imported = _resolve_sync_sets(
        registered_cameras,
        go2rtc_online,
        streams_index,
    )

    return {
        "go2rtc_online": go2rtc_online,
        "registered_cameras": registered_cameras,
        "go2rtc_streams": go2rtc_streams,
        "matched": matched,
        "missing_in_go2rtc": missing_in_go2rtc,
        "not_imported": not_imported,
    }


@app.post("/sync/import-go2rtc")
def sync_import_go2rtc() -> Dict[str, Any]:
    snapshot = go2rtc_client.get_streams_snapshot()
    if not snapshot["online"]:
        logger.warning("go2rtc_offline_sync_failed")
        raise HTTPException(status_code=503, detail="go2rtc offline: não foi possível importar streams")

    streams_index: Dict[str, Dict[str, Any]] = snapshot["streams"]
    existing_by_stream = {
        camera.get("stream_name"): camera
        for camera in registry_service.list_cameras()
        if camera.get("stream_name")
    }

    imported: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for stream_name, details in streams_index.items():
        if stream_name in existing_by_stream:
            logger.info("go2rtc_stream_skipped_existing stream=%s", stream_name)
            skipped.append({"stream_name": stream_name, "reason": "already_in_registry"})
            continue

        producers = details.get("producers") or []
        producer_url = ""
        if producers and isinstance(producers[0], dict):
            producer_url = producers[0].get("url") or ""

        camera = {
            "uuid": str(uuid.uuid4()),
            "name": stream_name,
            "source_type": "go2rtc",
            "source_url": producer_url,
            "stream_name": stream_name,
            "enabled": True,
            "video_wall": True,
            "plugins": ["YOLO"],
            "node": "auto",
            "created_at": _utc_now_iso(),
        }

        registry_service.add_camera(camera)
        logger.info("go2rtc_stream_imported stream=%s uuid=%s", stream_name, camera["uuid"])
        imported.append(camera)

    return {
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
    }


@app.get("/cameras/")
def get_all_cameras() -> List[Dict[str, Any]]:
    snapshot = go2rtc_client.get_streams_snapshot()
    go2rtc_online = bool(snapshot["online"])
    streams_index = snapshot["streams"]

    cameras = registry_service.list_cameras()
    return [_enrich_camera(camera, go2rtc_online, streams_index) for camera in cameras]


@app.get("/cameras/{uuid}")
def get_camera(uuid: str) -> Dict[str, Any]:
    camera = registry_service.get_camera(uuid)
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    snapshot = go2rtc_client.get_streams_snapshot()
    return _enrich_camera(camera, bool(snapshot["online"]), snapshot["streams"])


@app.post("/cameras/", status_code=201)
def add_camera(payload: CameraPayload) -> Dict[str, Any]:
    try:
        normalized_camera = _normalize_camera(payload)
        registry_service.add_camera(normalized_camera)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "UUID duplicado" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc

    snapshot = go2rtc_client.get_streams_snapshot()
    enriched = _enrich_camera(normalized_camera, bool(snapshot["online"]), snapshot["streams"])
    return {
        "status": "success",
        "camera": enriched,
        "observation": (
            "Cadastro persistido. Stream ainda não encontrado no go2rtc."
            if not enriched["go2rtc_registered"]
            else "Cadastro persistido e stream visível no go2rtc."
        ),
    }


@app.delete("/cameras/{uuid}")
def remove_camera(uuid: str) -> Dict[str, str]:
    if uuid in active_engines:
        active_engines[uuid].stop()
        del active_engines[uuid]

    if registry_service.remove_camera(uuid):
        return {"status": "deleted"}

    raise HTTPException(status_code=404, detail="Câmera não encontrada")


def frame_generator(uuid: str) -> Generator[bytes, None, None]:
    engine = active_engines.get(uuid)
    if not engine:
        camera = registry_service.get_camera(uuid)
        if not camera:
            return

        engine = CaptureEngine(
            camera_uuid=uuid,
            source_type=camera.get("source_type", ""),
            source_path=camera.get("source_url", ""),
        )
        active_engines[uuid] = engine

    stream = engine.start()
    if not stream:
        return

    try:
        for frame in stream:
            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
    finally:
        engine.stop()


@app.get("/stream/{uuid}")
def video_feed(uuid: str) -> StreamingResponse:
    camera = registry_service.get_camera(uuid)
    if not camera:
        raise HTTPException(status_code=404, detail="Stream não encontrado")

    return StreamingResponse(
        frame_generator(uuid),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"X-Stream-Mode": "legacy-fallback"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
