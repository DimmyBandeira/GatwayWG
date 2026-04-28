import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from onvif_bridge.config import load_config
from onvif_bridge.soap_templates import build_get_capabilities, build_get_stream_uri


def test_load_config_and_device_lookup(tmp_path: Path):
    cfg_file = tmp_path / "onvif_bridge_config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "gateway_ip": "192.168.10.100",
                "rtsp_port": 8554,
                "http_port": 8080,
                "auth_user": "admin",
                "auth_pass": "secret",
                "devices": [
                    {
                        "virtual_ip": "192.168.10.201",
                        "camera_uuid": "uuid-camera-1",
                        "name": "Camera Virtual 01",
                        "manufacturer": "GatwayWG",
                        "model": "Virtual ONVIF Camera",
                        "profile_token": "Profile_1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(str(cfg_file))
    device = cfg.get_device_by_virtual_ip("192.168.10.201")

    assert device is not None
    assert device.camera_uuid == "uuid-camera-1"
    assert len(cfg.sanitized_devices()) == 1


def test_soap_templates_include_expected_endpoints_and_rtsp_uri(tmp_path: Path):
    cfg_file = tmp_path / "onvif_bridge_config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "gateway_ip": "192.168.10.100",
                "rtsp_port": 8554,
                "http_port": 8080,
                "auth_user": "admin",
                "auth_pass": "secret",
                "devices": [
                    {
                        "virtual_ip": "192.168.10.201",
                        "camera_uuid": "uuid-camera-1",
                        "name": "Camera Virtual 01",
                        "manufacturer": "GatwayWG",
                        "model": "Virtual ONVIF Camera",
                        "profile_token": "Profile_1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(str(cfg_file))
    device = cfg.devices[0]

    capabilities_xml = build_get_capabilities(device, cfg)
    stream_uri_xml = build_get_stream_uri(device, cfg)

    assert "http://192.168.10.201:8080/onvif/device_service" in capabilities_xml
    assert "http://192.168.10.201:8080/onvif/media_service" in capabilities_xml
    assert "rtsp://admin:secret@192.168.10.100:8554/uuid-camera-1" in stream_uri_xml
