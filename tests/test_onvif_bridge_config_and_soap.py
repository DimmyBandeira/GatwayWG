import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from onvif_bridge.config import load_config
from onvif_bridge.soap_templates import (
    build_get_capabilities,
    build_get_hostname,
    build_get_network_interfaces,
    build_get_scopes,
    build_get_services,
    build_get_stream_uri,
    build_get_system_date_and_time,
    build_get_video_encoder_configurations,
)


def test_load_config_and_device_lookup(tmp_path: Path):
    cfg_file = tmp_path / "onvif_bridge_config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "gateway_ip": "192.168.10.100",
                "rtsp_port": 8554,
                "http_port": 8080,
                "auth_mode": "none",
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
    assert cfg.auth_mode == "none"
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

    capabilities_xml = build_get_capabilities(device, cfg, "192.168.10.201")
    stream_uri_xml = build_get_stream_uri(device, cfg)
    datetime_xml = build_get_system_date_and_time()
    hostname_xml = build_get_hostname(device)
    netif_xml = build_get_network_interfaces(device)
    scopes_xml = build_get_scopes()
    venc_xml = build_get_video_encoder_configurations()
    services_xml = build_get_services(device, cfg, "192.168.10.201")

    assert "http://192.168.10.201:8080/onvif/device_service" in capabilities_xml
    assert "http://192.168.10.201:8080/onvif/media_service" in capabilities_xml
    assert "<tt:RTPMulticast>false</tt:RTPMulticast>" in capabilities_xml
    assert "<tt:RTP_TCP>true</tt:RTP_TCP>" in capabilities_xml
    assert "<tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>" in capabilities_xml
    assert "rtsp://admin:secret@192.168.10.100:8554/uuid-camera-1" in stream_uri_xml
    assert "GetSystemDateAndTimeResponse" in datetime_xml
    assert "GetHostnameResponse" in hostname_xml
    assert "192.168.10.201" in netif_xml
    assert "GetScopesResponse" in scopes_xml
    assert "GetVideoEncoderConfigurationsResponse" in venc_xml
    assert "http://192.168.10.201:8080/onvif/device_service" in services_xml
    assert "http://192.168.10.201:8080/onvif/media_service" in services_xml
