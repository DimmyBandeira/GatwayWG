from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from integrations.go2rtc_client import Go2RTCClient
from services.capture_engine import CaptureEngine
from services.registry_service import RegistryService

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


def _normalize_camera(payload: CameraPayload) -> Dict[str, Any]:
    source_type = payload.source_type or payload.type
    source_url = payload.source_url or payload.path
    if not source_type or not source_url:
        raise ValueError("Campos obrigatórios ausentes: source_type/source_url")

    created_at = payload.created_at or payload.createdAt
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    video_wall = payload.video_wall
    if video_wall is None:
        video_wall = bool(payload.videoWall)

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


def _enrich_camera(camera: Dict[str, Any], streams_index: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    stream_name = camera.get("stream_name") or camera.get("uuid")
    urls = go2rtc_client.build_stream_urls(stream_name)

    registered: Optional[bool] = None
    if streams_index is not None:
        registered = stream_name in streams_index

    status_note = "stream_detected_in_go2rtc" if registered else "stream_not_found_in_go2rtc"
    if registered is None:
        status_note = "go2rtc_unavailable_or_unverified"

    payload = dict(camera)
    payload["urls"] = urls
    payload["go2rtc"] = {
        "registered": registered,
        "status": status_note,
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


@app.get("/cameras/")
def get_all_cameras() -> List[Dict[str, Any]]:
    streams_index = go2rtc_client.get_streams_index()
    cameras = registry_service.list_cameras()
    return [_enrich_camera(camera, streams_index) for camera in cameras]


@app.get("/cameras/{uuid}")
def get_camera(uuid: str) -> Dict[str, Any]:
    camera = registry_service.get_camera(uuid)
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    streams_index = go2rtc_client.get_streams_index()
    return _enrich_camera(camera, streams_index)


@app.post("/cameras/", status_code=201)
def add_camera(payload: CameraPayload) -> Dict[str, Any]:
    try:
        normalized_camera = _normalize_camera(payload)
        registry_service.add_camera(normalized_camera)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "UUID duplicado" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc

    streams_index = go2rtc_client.get_streams_index()
    enriched = _enrich_camera(normalized_camera, streams_index)
    return {
        "status": "success",
        "camera": enriched,
        "observation": (
            "Cadastro persistido. Stream ainda não encontrado no go2rtc."
            if enriched["go2rtc"]["registered"] is False
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
