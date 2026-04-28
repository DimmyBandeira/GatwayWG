from __future__ import annotations

from onvif_bridge.config import BridgeConfig, BridgeDevice


def soap_envelope(body_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
        'xmlns:trt="http://www.onvif.org/ver10/media/wsdl" '
        'xmlns:tt="http://www.onvif.org/ver10/schema">'
        f"<s:Body>{body_xml}</s:Body>"
        "</s:Envelope>"
    )


def build_get_device_information(device: BridgeDevice) -> str:
    return soap_envelope(
        "<tds:GetDeviceInformationResponse>"
        f"<tds:Manufacturer>{device.manufacturer}</tds:Manufacturer>"
        f"<tds:Model>{device.model}</tds:Model>"
        "<tds:FirmwareVersion>1.0.0</tds:FirmwareVersion>"
        f"<tds:SerialNumber>{device.camera_uuid}</tds:SerialNumber>"
        "<tds:HardwareId>GATWAYWG-ONVIF-BRIDGE</tds:HardwareId>"
        "</tds:GetDeviceInformationResponse>"
    )


def build_get_capabilities(device: BridgeDevice, cfg: BridgeConfig) -> str:
    device_xaddr = f"http://{device.virtual_ip}:{cfg.http_port}/onvif/device_service"
    media_xaddr = f"http://{device.virtual_ip}:{cfg.http_port}/onvif/media_service"
    return soap_envelope(
        "<tds:GetCapabilitiesResponse><tds:Capabilities>"
        "<tt:Device>"
        f"<tt:XAddr>{device_xaddr}</tt:XAddr>"
        "</tt:Device>"
        "<tt:Media>"
        f"<tt:XAddr>{media_xaddr}</tt:XAddr>"
        "</tt:Media>"
        "</tds:Capabilities></tds:GetCapabilitiesResponse>"
    )


def build_get_services(device: BridgeDevice, cfg: BridgeConfig) -> str:
    device_xaddr = f"http://{device.virtual_ip}:{cfg.http_port}/onvif/device_service"
    media_xaddr = f"http://{device.virtual_ip}:{cfg.http_port}/onvif/media_service"
    return soap_envelope(
        "<tds:GetServicesResponse>"
        "<tds:Service>"
        "<tds:Namespace>http://www.onvif.org/ver10/device/wsdl</tds:Namespace>"
        f"<tds:XAddr>{device_xaddr}</tds:XAddr>"
        "<tds:Version><tt:Major>2</tt:Major><tt:Minor>5</tt:Minor></tds:Version>"
        "</tds:Service>"
        "<tds:Service>"
        "<tds:Namespace>http://www.onvif.org/ver10/media/wsdl</tds:Namespace>"
        f"<tds:XAddr>{media_xaddr}</tds:XAddr>"
        "<tds:Version><tt:Major>2</tt:Major><tt:Minor>5</tt:Minor></tds:Version>"
        "</tds:Service>"
        "</tds:GetServicesResponse>"
    )


def build_get_profiles(device: BridgeDevice) -> str:
    return soap_envelope(
        "<trt:GetProfilesResponse>"
        f"<trt:Profiles token=\"{device.profile_token}\" fixed=\"true\">"
        f"<tt:Name>{device.name}</tt:Name>"
        "<tt:VideoSourceConfiguration token=\"VideoSourceConfig_1\">"
        "<tt:Name>VideoSourceConfig</tt:Name>"
        "<tt:UseCount>1</tt:UseCount>"
        "<tt:SourceToken>VideoSource_1</tt:SourceToken>"
        "</tt:VideoSourceConfiguration>"
        "</trt:Profiles>"
        "</trt:GetProfilesResponse>"
    )


def build_get_video_sources() -> str:
    return soap_envelope(
        "<trt:GetVideoSourcesResponse>"
        "<trt:VideoSources token=\"VideoSource_1\">"
        "<tt:Framerate>15</tt:Framerate>"
        "<tt:Resolution><tt:Width>1280</tt:Width><tt:Height>720</tt:Height></tt:Resolution>"
        "</trt:VideoSources>"
        "</trt:GetVideoSourcesResponse>"
    )


def build_get_stream_uri(device: BridgeDevice, cfg: BridgeConfig) -> str:
    uri = f"rtsp://{cfg.auth_user}:{cfg.auth_pass}@{cfg.gateway_ip}:{cfg.rtsp_port}/{device.camera_uuid}"
    return soap_envelope(
        "<trt:GetStreamUriResponse><trt:MediaUri>"
        f"<tt:Uri>{uri}</tt:Uri>"
        "<tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>"
        "<tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>"
        "<tt:Timeout>PT60S</tt:Timeout>"
        "</trt:MediaUri></trt:GetStreamUriResponse>"
    )


def build_fault(reason: str) -> str:
    return soap_envelope(
        "<s:Fault><s:Code><s:Value>s:Sender</s:Value></s:Code>"
        f"<s:Reason><s:Text xml:lang=\"en\">{reason}</s:Text></s:Reason></s:Fault>"
    )
