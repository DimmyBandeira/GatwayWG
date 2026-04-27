from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkHint:
    local_ip: str
    base_ip: str
    suggested_onvif_ports: list[int]
    suggested_rtsp_port: int


def _is_valid_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private and not addr.is_loopback and not addr.is_link_local and str(addr) != "0.0.0.0"
    except ValueError:
        return False


def _build_network_info(ip: str) -> dict[str, object]:
    parts = ip.split(".")
    base = ".".join(parts[:3]) + "."
    return {
        "local_ip": ip,
        "base_ip": base,
        "cidr": f"{base}0/24",
        "suggested_start": 1,
        "suggested_end": 254,
    }


def get_local_network_base() -> tuple[str, str]:
    networks = get_local_networks()
    first = networks[0]
    return str(first["local_ip"]), str(first["base_ip"])


def get_local_networks() -> list[dict[str, object]]:
    candidates: set[str] = set()

    # Principal interface discovery
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        candidates.add(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()

    # Additional host interfaces
    try:
        for family, *_rest, sockaddr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if family == socket.AF_INET and sockaddr:
                candidates.add(sockaddr[0])
    except OSError:
        pass

    valid = sorted({ip for ip in candidates if _is_valid_private_ip(ip)})
    if not valid:
        valid = ["192.168.1.10"]

    return [_build_network_info(ip) for ip in valid]


def get_network_hint() -> NetworkHint:
    local_ip, base_ip = get_local_network_base()
    return NetworkHint(
        local_ip=local_ip,
        base_ip=base_ip,
        suggested_onvif_ports=[80, 8080, 8000],
        suggested_rtsp_port=554,
    )
