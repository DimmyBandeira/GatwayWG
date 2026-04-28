from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple
import time

import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from integrations.go2rtc_client import Go2RTCClient
from services.camera_normalizer import normalize_stream_node, payload_has_fakepath, sanitize_plugins
from services.capture_engine import CaptureEngine
from services.go2rtc_discovery_service import Go2RTCDiscoveryService
from services.network_hint_service import get_local_networks, get_network_hint
from services.registry_service import RegistryService
from services.upload_service import save_video_upload

logger = logging.getLogger("GatewayApp")

app = FastAPI(title="WebGuardião Gateway Master", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STREAM_SLOTS: List[Tuple[str, str]] = [
    ("visible", "main"),
    ("visible", "sub"),
    ("thermal", "main"),
    ("thermal", "sub"),
]

registry_service = RegistryService()
go2rtc_client = Go2RTCClient()
go2rtc_discovery_service = Go2RTCDiscoveryService(go2rtc_client)
active_engines: Dict[str, CaptureEngine] = {}
provision_retry_lock = threading.Lock()
provision_retry_jobs: Dict[str, Dict[str, Any]] = {}
provision_retry_stop = threading.Event()
provision_retry_thread: Optional[threading.Thread] = None

PROVISION_RETRY_MAX_ATTEMPTS = 6
PROVISION_RETRY_BASE_DELAY_SECONDS = 5
PROVISION_RETRY_MAX_DELAY_SECONDS = 120


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
    streams: Optional[Dict[str, Any]] = None

    # Compatibilidade com contrato antigo
    type: Optional[str] = None
    path: Optional[str] = None
    videoWall: Optional[bool] = None
    createdAt: Optional[str] = None
    pipeline: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")




def _normalize_camera(payload: CameraPayload) -> Dict[str, Any]:
    created_at = payload.created_at or payload.createdAt or _utc_now_iso()
    video_wall = payload.video_wall if payload.video_wall is not None else bool(payload.videoWall)

    streams_payload = payload.streams if isinstance(payload.streams, dict) else {}
    visible_payload = streams_payload.get("visible", {}) if isinstance(streams_payload.get("visible", {}), dict) else {}
    thermal_payload = streams_payload.get("thermal", {}) if isinstance(streams_payload.get("thermal", {}), dict) else {}

    visible_main = normalize_stream_node(visible_payload.get("main"))
    visible_sub = normalize_stream_node(visible_payload.get("sub"))
    thermal_main = normalize_stream_node(thermal_payload.get("main"))
    thermal_sub = normalize_stream_node(thermal_payload.get("sub"))

    source_type = payload.source_type or payload.type
    source_url = payload.source_url if payload.source_url is not None else payload.path
    legacy_stream_name = payload.stream_name or payload.uuid

    if not visible_main and source_type:
        visible_main = {
            "stream_name": legacy_stream_name,
            "source_url": source_url or "",
        }

    if not any([visible_main, visible_sub, thermal_main, thermal_sub]):
        raise ValueError("Câmera sem stream definido (visible/thermal main/sub)")

    streams = {
        "visible": {"main": visible_main, "sub": visible_sub},
        "thermal": {"main": thermal_main, "sub": thermal_sub},
    }

    if payload_has_fakepath(streams, source_url or ""):
        raise ValueError("Caminho inválido: C:/fakepath não é acessível pelo servidor Gateway")

    has_visible = bool(visible_main and visible_main.get("stream_name"))
    has_visible_sub = bool(visible_sub and visible_sub.get("stream_name"))
    has_thermal = bool(thermal_main and thermal_main.get("stream_name"))
    has_thermal_sub = bool(thermal_sub and thermal_sub.get("stream_name"))

    stream_count = sum([has_visible, has_visible_sub, has_thermal, has_thermal_sub])

    primary_stream_name = visible_main.get("stream_name") if visible_main else None
    primary_source_url = visible_main.get("source_url", "") if visible_main else ""

    return {
        "uuid": payload.uuid,
        "name": payload.name,
        "has_visible": has_visible,
        "has_visible_sub": has_visible_sub,
        "has_thermal": has_thermal,
        "has_thermal_sub": has_thermal_sub,
        "stream_count": stream_count,
        "streams": streams,
        # Compatibilidade antiga
        "stream_name": primary_stream_name,
        "source_url": primary_source_url,
        "source_type": source_type or "go2rtc",
        "enabled": bool(payload.enabled) if payload.enabled is not None else True,
        "video_wall": bool(video_wall),
        "plugins": sanitize_plugins(payload.plugins),
        "node": payload.node or "auto",
        "created_at": created_at,
    }


def _iter_camera_streams(camera: Dict[str, Any]) -> List[Dict[str, Any]]:
    streams = camera.get("streams") or {}
    result: List[Dict[str, Any]] = []

    for modality, profile in STREAM_SLOTS:
        node = (streams.get(modality) or {}).get(profile)
        if not isinstance(node, dict):
            continue
        stream_name = node.get("stream_name")
        if not stream_name:
            continue
        result.append(
            {
                "camera_uuid": camera.get("uuid"),
                "camera_name": camera.get("name"),
                "modality": modality,
                "profile": profile,
                "stream_name": stream_name,
                "source_url": node.get("source_url", ""),
            }
        )
    return result


def _retry_job_key(camera_uuid: str, modality: str, profile: str) -> str:
    return f"{camera_uuid}:{modality}:{profile}"


def _retry_delay(attempt: int) -> int:
    return min(PROVISION_RETRY_BASE_DELAY_SECONDS * (2 ** max(0, attempt - 1)), PROVISION_RETRY_MAX_DELAY_SECONDS)


def _schedule_provision_retry(
    camera_uuid: str,
    modality: str,
    profile: str,
    stream_name: str,
    source_url: str,
    attempt: int,
    error: str = "",
) -> None:
    if attempt > PROVISION_RETRY_MAX_ATTEMPTS:
        return
    delay_seconds = _retry_delay(attempt)
    job = {
        "camera_uuid": camera_uuid,
        "modality": modality,
        "profile": profile,
        "stream_name": stream_name,
        "source_url": source_url,
        "attempt": attempt,
        "next_run_at": time.time() + delay_seconds,
        "last_error": error,
    }
    with provision_retry_lock:
        provision_retry_jobs[_retry_job_key(camera_uuid, modality, profile)] = job


def _run_provision_retry_worker() -> None:
    logger.info("provision_retry_worker_started")
    while not provision_retry_stop.is_set():
        now = time.time()
        due_jobs: List[Dict[str, Any]] = []
        with provision_retry_lock:
            for key, job in list(provision_retry_jobs.items()):
                if job.get("next_run_at", now + 1) <= now:
                    due_jobs.append(job)
                    provision_retry_jobs.pop(key, None)

        for job in due_jobs:
            result = go2rtc_client.upsert_stream(job["stream_name"], job["source_url"])
            if result.get("ok"):
                logger.info(
                    "provision_retry_success uuid=%s stream=%s modality=%s profile=%s attempt=%s",
                    job["camera_uuid"],
                    job["stream_name"],
                    job["modality"],
                    job["profile"],
                    job["attempt"],
                )
                continue

            next_attempt = int(job.get("attempt", 1)) + 1
            error_msg = str(result.get("error") or "unknown_error")
            _schedule_provision_retry(
                camera_uuid=job["camera_uuid"],
                modality=job["modality"],
                profile=job["profile"],
                stream_name=job["stream_name"],
                source_url=job["source_url"],
                attempt=next_attempt,
                error=error_msg,
            )
            logger.warning(
                "provision_retry_failed uuid=%s stream=%s modality=%s profile=%s attempt=%s/%s error=%s",
                job["camera_uuid"],
                job["stream_name"],
                job["modality"],
                job["profile"],
                next_attempt,
                PROVISION_RETRY_MAX_ATTEMPTS,
                error_msg,
            )

        provision_retry_stop.wait(1.0)
    logger.info("provision_retry_worker_stopped")


def _provision_camera_streams(camera: Dict[str, Any], schedule_retry: bool = True) -> Dict[str, Any]:
    source_type = str(camera.get("source_type") or "").lower()
    if source_type == "file":
        return {
            "attempted": False,
            "reason": "source_type_file",
            "results": [],
        }

    results: List[Dict[str, Any]] = []
    for stream in _iter_camera_streams(camera):
        stream_name = str(stream.get("stream_name") or "").strip()
        source_url = str(stream.get("source_url") or "").strip()
        if not stream_name or not source_url:
            continue

        upsert_result = go2rtc_client.upsert_stream(stream_name, source_url)
        if schedule_retry and not upsert_result.get("ok"):
            _schedule_provision_retry(
                camera_uuid=str(camera.get("uuid") or ""),
                modality=str(stream.get("modality") or ""),
                profile=str(stream.get("profile") or ""),
                stream_name=stream_name,
                source_url=source_url,
                attempt=1,
                error=str(upsert_result.get("error") or ""),
            )
        results.append(
            {
                "modality": stream.get("modality"),
                "profile": stream.get("profile"),
                **upsert_result,
            }
        )

    return {
        "attempted": bool(results),
        "results": results,
    }


def _provision_camera_uuid_alias(camera: Dict[str, Any], schedule_retry: bool = True) -> Dict[str, Any]:
    camera_uuid = str(camera.get("uuid") or "").strip()
    if not camera_uuid:
        return {"attempted": False, "action": "skipped_missing_uuid"}

    source_type = str(camera.get("source_type") or "").lower()
    if source_type == "file":
        return {"attempted": False, "action": "skipped_source_type_file"}

    for stream in _iter_camera_streams(camera):
        source_url = str(stream.get("source_url") or "").strip()
        if not source_url:
            continue

        result = go2rtc_client.upsert_stream(camera_uuid, source_url)
        if schedule_retry and not result.get("ok"):
            _schedule_provision_retry(
                camera_uuid=camera_uuid,
                modality="canonical",
                profile="uuid",
                stream_name=camera_uuid,
                source_url=source_url,
                attempt=1,
                error=str(result.get("error") or ""),
            )
        return {
            "attempted": True,
            "stream_name": camera_uuid,
            "source": {"modality": stream.get("modality"), "profile": stream.get("profile")},
            **result,
        }

    return {"attempted": False, "action": "skipped_missing_source_url"}


@app.on_event("startup")
def startup_event() -> None:
    global provision_retry_thread
    provision_retry_stop.clear()
    provision_retry_thread = threading.Thread(target=_run_provision_retry_worker, daemon=True, name="go2rtc-provision-retry")
    provision_retry_thread.start()
    for camera in registry_service.list_cameras():
        _provision_camera_uuid_alias(camera, schedule_retry=True)


@app.on_event("shutdown")
def shutdown_event() -> None:
    provision_retry_stop.set()
    if provision_retry_thread and provision_retry_thread.is_alive():
        provision_retry_thread.join(timeout=2)


def _resolve_sync_sets(
    cameras: List[Dict[str, Any]],
    go2rtc_online: bool,
    streams_index: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    camera_streams = [item for camera in cameras for item in _iter_camera_streams(camera)]
    if not go2rtc_online:
        for item in camera_streams:
            logger.info("camera_missing_in_go2rtc uuid=%s stream=%s", item.get("camera_uuid"), item.get("stream_name"))
        return [], camera_streams, []

    stream_names = set(streams_index.keys())
    matched = [item for item in camera_streams if item["stream_name"] in stream_names]
    missing_in_go2rtc = [item for item in camera_streams if item["stream_name"] not in stream_names]

    for item in missing_in_go2rtc:
        logger.info("camera_missing_in_go2rtc uuid=%s stream=%s", item.get("camera_uuid"), item.get("stream_name"))

    registry_stream_names = {item["stream_name"] for item in camera_streams}
    not_imported = [
        {"stream_name": stream_name, **(streams_index.get(stream_name) or {})}
        for stream_name in stream_names
        if stream_name not in registry_stream_names
    ]
    return matched, missing_in_go2rtc, not_imported


def _enrich_stream_node(
    node: Optional[Dict[str, Any]],
    go2rtc_online: bool,
    streams_index: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(node, dict):
        return None

    stream_name = node.get("stream_name")
    source_url = node.get("source_url", "")
    source_url_masked = go2rtc_client.mask_url(str(source_url))

    if not stream_name:
        return {
            "stream_name": None,
            "source_url": source_url_masked,
            "urls": None,
            "go2rtc_registered": False,
            "status_label": "not_published" if go2rtc_online else "go2rtc_offline",
        }

    go2rtc_registered = bool(go2rtc_online and stream_name in streams_index)
    if not go2rtc_online:
        status_label = "go2rtc_offline"
    elif go2rtc_registered:
        status_label = "online"
    else:
        status_label = "not_published"

    return {
        "stream_name": stream_name,
        "source_url": source_url_masked,
        "urls": go2rtc_client.build_stream_urls(stream_name),
        "go2rtc_registered": go2rtc_registered,
        "status_label": status_label,
    }


def _enrich_camera(camera: Dict[str, Any], go2rtc_online: bool, streams_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    streams = camera.get("streams") or {}
    visible = streams.get("visible") or {}
    thermal = streams.get("thermal") or {}

    visible_main = _enrich_stream_node(visible.get("main"), go2rtc_online, streams_index)
    visible_sub = _enrich_stream_node(visible.get("sub"), go2rtc_online, streams_index)
    thermal_main = _enrich_stream_node(thermal.get("main"), go2rtc_online, streams_index)
    thermal_sub = _enrich_stream_node(thermal.get("sub"), go2rtc_online, streams_index)

    enriched_streams = {
        "visible": {"main": visible_main, "sub": visible_sub},
        "thermal": {"main": thermal_main, "sub": thermal_sub},
    }

    has_visible = bool(visible_main and visible_main.get("stream_name"))
    has_visible_sub = bool(visible_sub and visible_sub.get("stream_name"))
    has_thermal = bool(thermal_main and thermal_main.get("stream_name"))
    has_thermal_sub = bool(thermal_sub and thermal_sub.get("stream_name"))
    stream_count = sum([has_visible, has_visible_sub, has_thermal, has_thermal_sub])

    primary = visible_main or visible_sub or thermal_main or thermal_sub

    payload = dict(camera)
    payload["streams"] = enriched_streams
    payload["has_visible"] = has_visible
    payload["has_visible_sub"] = has_visible_sub
    payload["has_thermal"] = has_thermal
    payload["has_thermal_sub"] = has_thermal_sub
    payload["stream_count"] = stream_count

    # compatibilidade legado
    payload["stream_name"] = (primary or {}).get("stream_name")
    payload["source_url"] = (primary or {}).get("source_url", "")
    payload["urls"] = (primary or {}).get("urls")
    payload["go2rtc_registered"] = bool((primary or {}).get("go2rtc_registered", False))
    payload["status_label"] = (primary or {}).get("status_label", "go2rtc_offline" if not go2rtc_online else "not_published")
    payload["go2rtc"] = {
        "registered": payload["go2rtc_registered"],
        "status": payload["status_label"],
    }
    camera_uuid = str(payload.get("uuid") or "").strip()
    payload["canonical_urls"] = (
        {
            **go2rtc_client.build_stream_urls(camera_uuid),
            "mjpeg_url": f"/stream/{camera_uuid}",
        }
        if camera_uuid
        else None
    )
    payload["canonical_status"] = {
        "camera_uuid": camera_uuid,
        "go2rtc_registered": bool(go2rtc_online and camera_uuid and camera_uuid in streams_index),
        "status_label": (
            "go2rtc_offline"
            if not go2rtc_online
            else ("online" if camera_uuid in streams_index else "not_published")
        ),
    }

    return payload


@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("cadastro.html")


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "online", "version": "2.0.0"}


@app.get("/network/local-base")
def network_local_base() -> Dict[str, Any]:
    hint = get_network_hint()
    return {
        "local_ip": hint.local_ip,
        "base_ip": hint.base_ip,
        "suggested_onvif_ports": hint.suggested_onvif_ports,
        "suggested_rtsp_port": hint.suggested_rtsp_port,
    }


@app.get("/network/local-networks")
def network_local_networks() -> Dict[str, Any]:
    return {"networks": get_local_networks()}


@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...)) -> Dict[str, str]:
    try:
        file_path = await save_video_upload(file)
    except ValueError as exc:
        msg = str(exc)
        status = 413 if "200MB" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar upload: {exc}") from exc

    return {"file_path": file_path}

@app.get("/go2rtc/health")
def go2rtc_health() -> Dict[str, Any]:
    return go2rtc_client.healthcheck()


@app.get("/go2rtc/streams")
def go2rtc_streams() -> List[Dict[str, Any]]:
    return go2rtc_client.get_active_streams()


@app.get("/go2rtc/discovery")
def go2rtc_discovery() -> Dict[str, Any]:
    # compatibilidade retroativa: retorna streams já cadastrados
    return go2rtc_discovery_service.discover_streams()


@app.get("/go2rtc/discovery/streams")
def go2rtc_discovery_streams() -> Dict[str, Any]:
    return go2rtc_discovery_service.discover_streams()


@app.get("/go2rtc/discovery/onvif")
def go2rtc_discovery_onvif(src: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    if not src:
        return {
            "online": True,
            "success": False,
            "timeout": False,
            "source": "go2rtc_onvif",
            "count": 0,
            "devices": [],
            "message": "Busca ONVIF geral é lenta/instável. Use busca direcionada por IP.",
            "hint": "onvif://user:pass@ip:porta",
        }

    return go2rtc_discovery_service.discover_onvif(src=src)


@app.get("/go2rtc/discovery/onvif/scan")
def go2rtc_discovery_onvif_scan(
    base_ip: str,
    start: int = Query(default=1, ge=1, le=254),
    end: int = Query(default=254, ge=1, le=254),
    port: int = Query(default=80, ge=1, le=65535),
    user: str = Query(..., min_length=1),
    password: str = Query(..., min_length=1),
    timeout_per_host: float = Query(default=3.0, ge=0.5, le=10.0),
    max_workers: int = Query(default=16, ge=1, le=64),
) -> Dict[str, Any]:
    if not base_ip.endswith("."):
        raise HTTPException(status_code=400, detail="base_ip inválido. Exemplo: 192.168.1.")

    if end < start:
        raise HTTPException(status_code=400, detail="Faixa inválida: end deve ser >= start")

    def scan_one(host: int) -> Dict[str, Any]:
        ip = f"{base_ip}{host}"
        src = f"onvif://{user}:{password}@{ip}:{port}"
        result = go2rtc_client.discover_onvif(src=src, timeout_seconds=timeout_per_host)
        return {"ip": ip, "result": result}

    devices: List[Dict[str, Any]] = []
    timeout_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scan_one, host) for host in range(start, end + 1)]
        for fut in as_completed(futures):
            item = fut.result()
            ip = item["ip"]
            result = item["result"]

            if not result.get("success"):
                if result.get("timeout"):
                    timeout_count += 1
                else:
                    failed_count += 1
                continue

            streams = result.get("streams") if isinstance(result.get("streams"), list) else []
            if not streams:
                failed_count += 1
                continue

            first = streams[0] if isinstance(streams[0], dict) else {}
            devices.append(
                {
                    "ip": ip,
                    "port": port,
                    "name": first.get("name") or first.get("stream_name") or ip,
                    "streams": streams,
                    "raw": result.get("raw", {}),
                }
            )

    return {
        "source": "go2rtc_onvif_scan",
        "base_ip": base_ip,
        "start": start,
        "end": end,
        "port": port,
        "count": len(devices),
        "devices": devices,
        "failed_count": failed_count,
        "timeout_count": timeout_count,
    }


@app.get("/sync/status")
def sync_status() -> Dict[str, Any]:
    logger.info("sync_status_requested")
    registered_cameras = registry_service.list_cameras()
    snapshot = go2rtc_client.get_streams_snapshot()
    go2rtc_online = bool(snapshot["online"])
    streams_index = snapshot["streams"]

    go2rtc_streams = (
        [{"stream_name": stream_name, **(details or {})} for stream_name, details in streams_index.items()]
        if go2rtc_online
        else []
    )

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
    existing_stream_names = {
        item["stream_name"]
        for camera in registry_service.list_cameras()
        for item in _iter_camera_streams(camera)
    }

    imported: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for stream_name, details in streams_index.items():
        if stream_name in existing_stream_names:
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
            "has_visible": True,
            "has_visible_sub": False,
            "has_thermal": False,
            "has_thermal_sub": False,
            "stream_count": 1,
            "streams": {
                "visible": {
                    "main": {
                        "stream_name": stream_name,
                        "source_url": producer_url,
                    },
                    "sub": None,
                },
                "thermal": {"main": None, "sub": None},
            },
            "stream_name": stream_name,
            "source_url": producer_url,
            "source_type": "go2rtc",
            "enabled": True,
            "video_wall": False,
            "plugins": [],
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

    provisioning = _provision_camera_streams(normalized_camera)
    canonical_provisioning = _provision_camera_uuid_alias(normalized_camera, schedule_retry=True)

    snapshot = go2rtc_client.get_streams_snapshot()
    enriched = _enrich_camera(normalized_camera, bool(snapshot["online"]), snapshot["streams"])

    has_provision_failure = any(not item.get("ok", False) for item in provisioning.get("results", []))
    observation = (
        "Cadastro persistido. Verifique status por stream em camera.streams.*"
        if not has_provision_failure
        else "Cadastro persistido, mas um ou mais streams não foram publicados no go2rtc."
    )

    return {
        "status": "success",
        "camera": enriched,
        "observation": observation,
        "go2rtc_provisioning": provisioning,
        "canonical_uuid_provisioning": canonical_provisioning,
    }


@app.post("/cameras/{uuid}/publish")
def publish_camera_streams(uuid: str) -> Dict[str, Any]:
    camera = registry_service.get_camera(uuid)
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    provisioning = _provision_camera_streams(camera, schedule_retry=True)
    canonical_provisioning = _provision_camera_uuid_alias(camera, schedule_retry=True)
    snapshot = go2rtc_client.get_streams_snapshot()
    enriched = _enrich_camera(camera, bool(snapshot["online"]), snapshot["streams"])

    return {
        "status": "success",
        "camera": enriched,
        "go2rtc_provisioning": provisioning,
        "canonical_uuid_provisioning": canonical_provisioning,
    }


@app.get("/cameras/{uuid}/urls")
def get_camera_urls(uuid: str) -> Dict[str, Any]:
    camera = registry_service.get_camera(uuid)
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    snapshot = go2rtc_client.get_streams_snapshot()
    go2rtc_online = bool(snapshot["online"])
    streams_index = snapshot["streams"]
    enriched = _enrich_camera(camera, go2rtc_online, streams_index)

    return {
        "uuid": uuid,
        "canonical_urls": enriched.get("canonical_urls"),
        "canonical_status": enriched.get("canonical_status"),
        "streams": enriched.get("streams"),
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

        source_url = camera.get("source_url", "")
        source_type = camera.get("source_type", "")

        engine = CaptureEngine(
            camera_uuid=uuid,
            source_type=source_type,
            source_path=source_url,
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
