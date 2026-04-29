import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import onvif_bridge.main as bridge_main
from onvif_bridge.config import BridgeConfigError


def test_last_requests_ring_buffer_limit_and_clear():
    with bridge_main.LAST_REQUESTS_LOCK:
        bridge_main.LAST_REQUESTS.clear()

    for idx in range(60):
        bridge_main._register_request_log({"idx": idx})

    payload = bridge_main.bridge_debug_last_requests()
    assert payload["count"] == 50
    assert payload["items"][0]["idx"] == 59
    assert payload["items"][-1]["idx"] == 10

    cleared = bridge_main.bridge_debug_clear_last_requests()
    assert cleared["status"] == "cleared"
    assert bridge_main.bridge_debug_last_requests()["count"] == 0


def test_fallback_config_when_file_missing(monkeypatch):
    bridge_main.get_bridge_config.cache_clear()
    monkeypatch.setattr(bridge_main, "load_config", lambda: (_ for _ in ()).throw(BridgeConfigError("missing")))

    cfg = bridge_main.get_bridge_config()
    assert cfg.http_port == 8080
    assert cfg.devices == []
    assert cfg.auth_mode == "none"
    assert bridge_main.bridge_health() == {"status": "ok"}


def test_permissive_handshake_operations():
    assert bridge_main._is_permissive_handshake_operation("GetSystemDateAndTime") is True
    assert bridge_main._is_permissive_handshake_operation("SetSystemDateAndTime") is True
    assert bridge_main._is_permissive_handshake_operation("GetServices") is True
    assert bridge_main._is_permissive_handshake_operation("GetCapabilities") is True
    assert bridge_main._is_permissive_handshake_operation("GetDeviceInformation") is True
    assert bridge_main._is_permissive_handshake_operation("GetScopes") is True
    assert bridge_main._is_permissive_handshake_operation("GetProfiles") is True
    assert bridge_main._is_permissive_handshake_operation("GetVideoSources") is True
    assert bridge_main._is_permissive_handshake_operation("GetVideoEncoderConfigurations") is True
    assert bridge_main._is_permissive_handshake_operation("GetStreamUri") is True


def test_dispatch_set_system_date_and_time_noop_response():
    cfg = bridge_main.get_bridge_config()
    device = bridge_main.BridgeDevice(
        virtual_ip="192.168.10.201",
        camera_uuid="uuid-camera-1",
        name="Cam 1",
        manufacturer="GatwayWG",
        model="Virtual ONVIF Camera",
        profile_token="Profile_1",
        channel=1,
        main_subtype=0,
        sub_subtype=1,
        rtsp_profile_mode="uuid",
    )
    status_code, xml = bridge_main._dispatch_onvif("SetSystemDateAndTime", device, cfg, "192.168.10.201")
    assert status_code == 200
    assert "SetSystemDateAndTimeResponse" in xml


def test_detect_operation_get_scopes():
    xml = """
    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
      <s:Body>
        <tds:GetScopes xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>
      </s:Body>
    </s:Envelope>
    """
    assert bridge_main._detect_operation(xml) == "GetScopes"


def test_detect_operation_details_for_media_variants():
    xml = """
    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
      <s:Body>
        <trt:GetVideoEncoderConfigurationOptions xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>
      </s:Body>
    </s:Envelope>
    """
    operation, detected_by = bridge_main._detect_operation_details(xml)
    assert operation == "GetVideoEncoderConfigurationOptions"
    assert detected_by == "operation_name_scan"


def test_detect_operation_details_fallback_to_first_tag():
    xml = """
    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
      <s:Body>
        <trt:VendorSpecificMediaOp xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>
      </s:Body>
    </s:Envelope>
    """
    operation, detected_by = bridge_main._detect_operation_details(xml)
    assert operation == "VendorSpecificMediaOp"
    assert detected_by == "soap_body_first_tag"

