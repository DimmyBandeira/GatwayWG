from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkHint:
    local_ip: str
    base_ip: str
    suggested_onvif_ports: list[int]
    suggested_rtsp_port: int


def get_local_network_base() -> tuple[str, str]:
    fallback_ip = "192.168.1.10"
    fallback_base = "192.168.1."

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
        parts = local_ip.split(".")
        if len(parts) == 4:
            base_ip = ".".join(parts[:3]) + "."
            return local_ip, base_ip
        return local_ip, fallback_base
    except OSError:
        return fallback_ip, fallback_base
    finally:
        sock.close()


def get_network_hint() -> NetworkHint:
    local_ip, base_ip = get_local_network_base()
    return NetworkHint(
        local_ip=local_ip,
        base_ip=base_ip,
        suggested_onvif_ports=[80, 8080, 8000],
        suggested_rtsp_port=554,
    )
