import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("cv2", object())

import app as gateway_app  # noqa: E402


def test_build_go2rtc_source_normalizes_exec_file_input():
    camera = {"source_type": "file"}
    stream = {
        "stream_name": "cam-main",
        "source_url": "exec:ffmpeg -re -stream_loop -1 -i /videos/demo.mp4 -c copy -f rtsp rtsp://localhost:8554/cam-main",
    }
    source = gateway_app._build_go2rtc_source(camera, stream)
    assert source == "exec:ffmpeg -re -stream_loop -1 -i /videos/demo.mp4 -c copy -rtsp_transport tcp -f rtsp {output}"


def test_go2rtc_stream_diagnostics_happy_path(monkeypatch):
    camera_uuid = "cam-uuid-1"
    camera = {
        "uuid": camera_uuid,
        "streams": {"visible": {"main": {"stream_name": "base-stream", "source_url": "rtsp://src"}, "sub": None}, "thermal": {"main": None, "sub": None}},
    }

    monkeypatch.setattr(gateway_app.registry_service, "get_camera", lambda _uuid: camera if _uuid == camera_uuid else None)
    monkeypatch.setattr(
        gateway_app.go2rtc_client,
        "get_streams_snapshot",
        lambda: {
            "online": True,
            "streams": {
                "base-stream": {"producers": [{"url": "rtsp://upstream/base-stream", "type": "rtsp"}]},
                camera_uuid: {"producers": [{"url": "rtsp://127.0.0.1:8554/base-stream", "type": "rtsp"}]},
            },
        },
    )

    payload = gateway_app.go2rtc_stream_diagnostics(camera_uuid)
    assert payload["checks"]["base_stream_ok"] is True
    assert payload["checks"]["alias_ok"] is True
    assert payload["base_stream"]["name"] == "base-stream"
    assert payload["uuid_alias"]["registered"] is True
