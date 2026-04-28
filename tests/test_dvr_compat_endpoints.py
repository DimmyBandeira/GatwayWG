import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("cv2", types.SimpleNamespace(imencode=lambda *_args, **_kwargs: (True, b"")))
pytest.importorskip("fastapi")

import app as gateway_app  # noqa: E402


def test_dvr_compat_onvif_info_contract():
    payload = gateway_app.dvr_compat_onvif_info()

    assert "onvif_endpoint" in payload
    assert payload["rtsp_port"] == 8554
    assert payload["transport"] == "tcp"
    assert payload["auth_required"] is True
    assert any("ONVIF" in note for note in payload["notes"])


def test_dvr_compat_test_instructions_contains_operator_steps():
    payload = gateway_app.dvr_compat_test_instructions()

    assert "steps" in payload
    assert any("protocolo ONVIF" in step for step in payload["steps"])
    assert any("1984" in step for step in payload["steps"])
    assert payload["expected_rtsp_contract"] == "rtsp://<gateway_ip>:8554/<camera_uuid>"
