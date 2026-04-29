from __future__ import annotations

import base64
import logging
import os
import re
from collections import deque
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from onvif_bridge.config import BridgeConfig, BridgeConfigError, BridgeDevice, load_config
    from onvif_bridge.soap_templates import (
        build_fault,
        build_get_capabilities,
        build_get_device_information,
        build_get_hostname,
        build_get_network_interfaces,
        build_get_profiles,
        build_get_scopes,
        build_get_services,
        build_get_stream_uri,
        build_get_system_date_and_time,
        build_get_video_encoder_configurations,
        build_get_video_sources,
    )
else:
    from .config import BridgeConfig, BridgeConfigError, BridgeDevice, load_config
    from .soap_templates import (
        build_fault,
        build_get_capabilities,
        build_get_device_information,
        build_get_hostname,
        build_get_network_interfaces,
        build_get_profiles,
        build_get_scopes,
        build_get_services,
        build_get_stream_uri,
        build_get_system_date_and_time,
        build_get_video_encoder_configurations,
        build_get_video_sources,
    )

logger = logging.getLogger("onvif_bridge")
app = FastAPI(title="GatwayWG ONVIF Bridge", version="0.2.0")
LAST_REQUESTS: deque[dict[str, Any]] = deque(maxlen=50)
LAST_REQUESTS_LOCK = Lock()


@lru_cache(maxsize=1)
def get_bridge_config() -> BridgeConfig:
    try:
        return load_config()
    except BridgeConfigError as exc:
        logger.warning("Falha ao carregar configuração do ONVIF Bridge: %s", exc)
        default_port = int(os.getenv("ONVIF_BRIDGE_HTTP_PORT", "8080"))
        return BridgeConfig(
            gateway_ip="127.0.0.1",
            rtsp_port=8554,
            http_port=default_port,
            auth_user="admin",
            auth_pass="CHANGE_ME",
            auth_mode="none",
            devices=[],
        )


@app.on_event("startup")
def on_startup() -> None:
    cfg = get_bridge_config()
    logger.info("ONVIF Bridge iniciado com sucesso na porta %s", cfg.http_port)


def _mask_rtsp(uri: str) -> str:
    if "@" not in uri or ":" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    if "@" not in rest or ":" not in rest.split("@", 1)[0]:
        return uri
    creds, suffix = rest.split("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{suffix}"


def _resolve_virtual_ip(request: Request) -> str:
    host_header = request.headers.get("host", "").strip()
    if host_header:
        return host_header.split(":", 1)[0]
    return request.url.hostname or ""


def _detect_wsse_username_token(xml_body: str) -> bool:
    return "UsernameToken" in xml_body or "wsse:UsernameToken" in xml_body


def _sanitize_text(text: str, cfg: BridgeConfig) -> str:
    sanitized = text or ""
    if cfg.auth_pass:
        sanitized = sanitized.replace(cfg.auth_pass, "***")
    sanitized = re.sub(r"(<[^>]*Password[^>]*>)(.*?)(</[^>]*Password[^>]*>)", r"\1***\3", sanitized, flags=re.IGNORECASE)
    return sanitized


def _limited_body_for_log(body: str, cfg: BridgeConfig, limit: int = 1000) -> str:
    sanitized = _sanitize_text(body, cfg)
    if len(sanitized) <= limit:
        return sanitized
    return sanitized[:limit] + "...<truncated>"


def _register_request_log(entry: dict[str, Any]) -> None:
    with LAST_REQUESTS_LOCK:
        LAST_REQUESTS.appendleft(entry)


def _get_device_or_404(request: Request, cfg: BridgeConfig) -> BridgeDevice:
    virtual_ip = _resolve_virtual_ip(request)
    device = cfg.get_device_by_virtual_ip(virtual_ip)
    if device is None:
        logger.warning("virtual_ip_not_mapped ip=%s path=%s", virtual_ip, request.url.path)
        raise HTTPException(status_code=404, detail="virtual_ip não mapeado")
    return device


def _parse_basic_auth(header_value: str | None) -> tuple[str, str] | None:
    if not header_value or not header_value.lower().startswith("basic "):
        return None
    raw = header_value.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
    except Exception:
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


def _enforce_auth(request: Request, cfg: BridgeConfig) -> None:
    if cfg.auth_mode == "none":
        return

    parsed = _parse_basic_auth(request.headers.get("authorization"))
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="autenticação obrigatória",
            headers={"WWW-Authenticate": "Basic"},
        )

    username, password = parsed
    if username != cfg.auth_user or password != cfg.auth_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )


def _detect_operation(xml_body: str) -> str:
    operations = [
        "GetSystemDateAndTime",
        "GetHostname",
        "GetNetworkInterfaces",
        "GetScopes",
        "GetDeviceInformation",
        "GetCapabilities",
        "GetServices",
        "GetProfiles",
        "GetVideoSources",
        "GetVideoEncoderConfigurations",
        "GetStreamUri",
    ]
    for operation in operations:
        if operation in xml_body:
            return operation
    return "unknown"


def _dispatch_onvif(operation: str, device: BridgeDevice, cfg: BridgeConfig, service_host: str) -> tuple[int, str]:
    if operation == "GetSystemDateAndTime":
        return 200, build_get_system_date_and_time()
    if operation == "GetHostname":
        return 200, build_get_hostname(device)
    if operation == "GetNetworkInterfaces":
        return 200, build_get_network_interfaces(device)
    if operation == "GetScopes":
        return 200, build_get_scopes()
    if operation == "GetDeviceInformation":
        return 200, build_get_device_information(device)
    if operation == "GetCapabilities":
        return 200, build_get_capabilities(device, cfg, service_host)
    if operation == "GetServices":
        return 200, build_get_services(device, cfg, service_host)
    if operation == "GetProfiles":
        return 200, build_get_profiles(device)
    if operation == "GetVideoSources":
        return 200, build_get_video_sources()
    if operation == "GetVideoEncoderConfigurations":
        return 200, build_get_video_encoder_configurations()
    if operation == "GetStreamUri":
        return 200, build_get_stream_uri(device, cfg)
    return 400, build_fault("Unsupported operation")


@app.middleware("http")
async def request_logger_middleware(request: Request, call_next):
    cfg = get_bridge_config()
    body = (await request.body()).decode("utf-8", errors="ignore")
    operation = _detect_operation(body)
    host = request.headers.get("host", "").split(":", 1)[0]
    client_ip = request.client.host if request.client else ""
    soap_action_header = request.headers.get("soapaction")
    content_type = request.headers.get("content-type", "")
    body_preview = _limited_body_for_log(body, cfg)

    request.state.detected_operation = operation

    logger.info(
        "request_received method=%s path=%s host=%s client_ip=%s",
        request.method,
        request.url.path,
        host,
        client_ip,
    )
    response = await call_next(request)

    _register_request_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "method": request.method,
            "path": request.url.path,
            "host": host,
            "client_ip": client_ip,
            "content_type": content_type,
            "soap_action_header": soap_action_header,
            "soap_operation_detected": operation,
            "body_preview": body_preview,
            "status_code": response.status_code,
        }
    )

    return response


@app.get("/onvif-bridge/health")
def bridge_health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/onvif-bridge/devices")
def bridge_devices() -> dict[str, Any]:
    cfg = get_bridge_config()
    return {"devices": cfg.sanitized_devices()}


@app.get("/onvif-bridge/debug/last-requests")
def bridge_debug_last_requests() -> dict[str, Any]:
    with LAST_REQUESTS_LOCK:
        items = list(LAST_REQUESTS)
    return {"count": len(items), "items": items}


@app.delete("/onvif-bridge/debug/last-requests")
def bridge_debug_clear_last_requests() -> dict[str, Any]:
    with LAST_REQUESTS_LOCK:
        LAST_REQUESTS.clear()
    return {"status": "cleared", "count": 0}


async def _handle_onvif_request(request: Request) -> Response:
    cfg = get_bridge_config()
    body = (await request.body()).decode("utf-8", errors="ignore")

    operation = getattr(request.state, "detected_operation", _detect_operation(body))
    wsse_present = _detect_wsse_username_token(body)
    host = request.headers.get("host", "").split(":", 1)[0]
    client_ip = request.client.host if request.client else ""
    body_preview = _limited_body_for_log(body, cfg)

    try:
        _enforce_auth(request, cfg)
        device = _get_device_or_404(request, cfg)
    except HTTPException as exc:
        logger.warning(
            "onvif_request_rejected method=%s path=%s host=%s client_ip=%s action=%s status=%s wsse=%s body=%s",
            request.method,
            request.url.path,
            host,
            client_ip,
            operation,
            exc.status_code,
            wsse_present,
            body_preview,
        )
        raise

    status_code, xml = _dispatch_onvif(operation, device, cfg, device.virtual_ip)
    masked_stream = _mask_rtsp(f"rtsp://{cfg.auth_user}:{cfg.auth_pass}@{cfg.gateway_ip}:{cfg.rtsp_port}/{device.camera_uuid}")
    device_xaddr = f"http://{device.virtual_ip}:{cfg.http_port}/onvif/device_service"
    media_xaddr = f"http://{device.virtual_ip}:{cfg.http_port}/onvif/media_service"

    logger.info(
        "onvif_request_ok method=%s path=%s host=%s client_ip=%s op=%s virtual_ip=%s uuid=%s wsse=%s auth_mode=%s device_xaddr=%s media_xaddr=%s stream=%s body=%s",
        request.method,
        request.url.path,
        host,
        client_ip,
        operation,
        device.virtual_ip,
        device.camera_uuid,
        wsse_present,
        cfg.auth_mode,
        device_xaddr,
        media_xaddr,
        masked_stream,
        body_preview,
    )

    return Response(content=xml, media_type="application/soap+xml; charset=utf-8", status_code=status_code)


@app.post("/onvif/device_service")
@app.post("/onvif/device_service/")
@app.post("/onvif/Device")
@app.post("/onvif/device")
async def onvif_device_service(request: Request) -> Response:
    return await _handle_onvif_request(request)


@app.post("/onvif/media_service")
@app.post("/onvif/media_service/")
@app.post("/onvif/Media")
@app.post("/onvif/media")
async def onvif_media_service(request: Request) -> Response:
    return await _handle_onvif_request(request)


if __name__ == "__main__":
    import uvicorn

    cfg = get_bridge_config()
    logger.info("ONVIF Bridge iniciado com sucesso na porta %s", cfg.http_port)
    uvicorn.run(app, host="0.0.0.0", port=cfg.http_port)
