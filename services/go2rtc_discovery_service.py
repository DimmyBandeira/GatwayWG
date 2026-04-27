from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from integrations.go2rtc_client import Go2RTCClient


@dataclass(frozen=True)
class DiscoveredGo2RTCStream:
    stream_name: str
    source_url: str | None
    source_scheme: str | None
    host: str | None
    is_rtsp: bool
    is_file_or_exec: bool
    consumers_count: int
    producers_count: int
    suggested_name: str
    suggested_source_type: str


class Go2RTCDiscoveryService:
    """Discovery operacional de streams cadastrados e ONVIF via go2rtc."""

    def __init__(self, client: Go2RTCClient | None = None) -> None:
        self._client = client or Go2RTCClient()

    def discover(self) -> dict[str, Any]:
        """Compatibilidade retroativa com o endpoint legado /go2rtc/discovery."""
        return self.discover_streams()

    def discover_streams(self) -> dict[str, Any]:
        snapshot = self._client.get_streams_snapshot()
        online = bool(snapshot.get("online", False))
        streams_map = snapshot.get("streams")

        if not online or not isinstance(streams_map, dict):
            return {
                "online": False,
                "source": "go2rtc_streams",
                "streams": [],
                "count": 0,
                "message": "go2rtc offline ou indisponível",
            }

        normalized = [
            self._normalize_stream(stream_name, details)
            for stream_name, details in streams_map.items()
        ]

        return {
            "online": True,
            "source": "go2rtc_streams",
            "count": len(normalized),
            "streams": [self._to_stream_dict(item) for item in normalized],
        }

    def discover_onvif(self, src: str | None = None) -> dict[str, Any]:
        result = self._client.discover_onvif(src)
        online = bool(result.get("online", False))
        raw_streams = result.get("streams") if isinstance(result.get("streams"), list) else []

        if not online:
            return {
                "online": False,
                "source": "go2rtc_onvif",
                "count": 0,
                "devices": [],
                "message": "go2rtc offline ou indisponível",
            }

        devices = [self._normalize_onvif_device(item) for item in raw_streams]

        return {
            "online": True,
            "source": "go2rtc_onvif",
            "count": len(devices),
            "devices": devices,
        }

    def _normalize_stream(self, stream_name: str, details: Any) -> DiscoveredGo2RTCStream:
        item = details if isinstance(details, dict) else {}
        producers = item.get("producers") if isinstance(item.get("producers"), list) else []
        consumers = item.get("consumers") if isinstance(item.get("consumers"), list) else []

        source_url = self._extract_first_producer_url(producers)
        parsed = urlparse(source_url) if source_url else None

        scheme = parsed.scheme if parsed else None
        host = parsed.hostname if parsed else None
        is_rtsp = scheme == "rtsp"
        is_file_or_exec = bool(
            source_url
            and (
                source_url.startswith("exec:")
                or source_url.startswith("file:")
                or source_url.lower().endswith((".mp4", ".avi", ".mkv"))
            )
        )

        return DiscoveredGo2RTCStream(
            stream_name=stream_name,
            source_url=source_url,
            source_scheme=scheme,
            host=host,
            is_rtsp=is_rtsp,
            is_file_or_exec=is_file_or_exec,
            consumers_count=len(consumers),
            producers_count=len(producers),
            suggested_name=stream_name,
            suggested_source_type="go2rtc",
        )

    def _normalize_onvif_device(self, item: Any) -> dict[str, Any]:
        raw = item if isinstance(item, dict) else {}
        name = str(raw.get("name") or raw.get("stream_name") or "onvif_device").strip()
        url = str(raw.get("url") or raw.get("source") or "").strip() or None
        rtsp_url = str(raw.get("rtsp") or raw.get("rtsp_url") or "").strip() or None

        parsed = urlparse(url) if url else None
        host = parsed.hostname if parsed else None

        if not rtsp_url and url and url.startswith("rtsp://"):
            rtsp_url = url

        return {
            "name": name,
            "url": url,
            "host": host,
            "rtsp_url": rtsp_url,
            "raw": raw,
            "actions": {
                "use_as_visible_main": {"role": "visible", "profile": "main"},
                "use_as_thermal_main": {"role": "thermal", "profile": "main"},
            },
        }

    @staticmethod
    def _extract_first_producer_url(producers: list[Any]) -> str | None:
        for producer in producers:
            if not isinstance(producer, dict):
                continue
            url = producer.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
        return None

    @staticmethod
    def _to_stream_dict(item: DiscoveredGo2RTCStream) -> dict[str, Any]:
        return {
            "stream_name": item.stream_name,
            "source_url": item.source_url,
            "source_scheme": item.source_scheme,
            "host": item.host,
            "is_rtsp": item.is_rtsp,
            "is_file_or_exec": item.is_file_or_exec,
            "consumers_count": item.consumers_count,
            "producers_count": item.producers_count,
            "suggested_name": item.suggested_name,
            "suggested_source_type": item.suggested_source_type,
            "actions": {
                "use_as_visible_main": {"role": "visible", "profile": "main"},
                "use_as_visible_sub": {"role": "visible", "profile": "sub"},
                "use_as_thermal_main": {"role": "thermal", "profile": "main"},
                "use_as_thermal_sub": {"role": "thermal", "profile": "sub"},
            },
        }
