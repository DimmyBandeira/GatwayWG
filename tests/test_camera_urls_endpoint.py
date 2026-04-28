import sys
import types
from pathlib import Path

import pytest

# app.py importa cv2 no módulo. Para testes unitários de endpoint, criamos um stub leve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("cv2", types.SimpleNamespace(imencode=lambda *_args, **_kwargs: (True, b"")))
pytest.importorskip("fastapi")

import app as gateway_app  # noqa: E402


def test_get_camera_urls_returns_canonical_fields(monkeypatch):
    camera_uuid = "cam-uuid-001"
    camera = {
        "uuid": camera_uuid,
        "name": "cam teste",
        "source_type": "rtsp",
        "streams": {
            "visible": {
                "main": {
                    "stream_name": "orig-stream-main",
                    "source_url": "rtsp://admin:senha@192.168.1.20:554/Streaming/Channels/101",
                },
                "sub": None,
            },
            "thermal": {"main": None, "sub": None},
        },
        "has_visible": True,
        "has_visible_sub": False,
        "has_thermal": False,
        "has_thermal_sub": False,
        "stream_count": 1,
        "enabled": True,
        "video_wall": False,
        "plugins": [],
        "node": "auto",
        "created_at": "2026-01-01T00:00:00Z",
    }

    monkeypatch.setattr(gateway_app.registry_service, "get_camera", lambda _uuid: camera)
    monkeypatch.setattr(
        gateway_app.go2rtc_client,
        "get_streams_snapshot",
        lambda: {
            "online": True,
            "streams": {
                camera_uuid: {"producers": [], "consumers": []},
                "orig-stream-main": {"producers": [], "consumers": []},
            },
        },
    )

    payload = gateway_app.get_camera_urls(camera_uuid)

    assert payload["uuid"] == camera_uuid
    assert payload["canonical_urls"]["rtsp_url"].endswith(f"/{camera_uuid}")
    assert payload["canonical_urls"]["webrtc_url"].endswith(f"src={camera_uuid}")
    assert payload["canonical_status"]["status_label"] == "online"
    assert payload["canonical_status"]["go2rtc_registered"] is True
