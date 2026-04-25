"""Cliente de integração com API do go2rtc."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from config import (
    GO2RTC_API_BASE_URL,
    GO2RTC_RTSP_HOST,
    GO2RTC_RTSP_PORT,
    GO2RTC_WEBRTC_HOST,
    GO2RTC_WEBRTC_PORT,
)

logger = logging.getLogger("Go2RTCClient")


class Go2RTCClient:
    """Ponte entre o Gateway Python e o middleware go2rtc."""

    def __init__(
        self,
        base_url: str = GO2RTC_API_BASE_URL,
        rtsp_host: str = GO2RTC_RTSP_HOST,
        rtsp_port: int = GO2RTC_RTSP_PORT,
        webrtc_host: str = GO2RTC_WEBRTC_HOST,
        webrtc_port: int = GO2RTC_WEBRTC_PORT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.rtsp_host = rtsp_host
        self.rtsp_port = rtsp_port
        self.webrtc_host = webrtc_host
        self.webrtc_port = webrtc_port

    def healthcheck(self) -> Dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}/api/streams", timeout=3)
            response.raise_for_status()
            return {"online": True, "api_base_url": self.base_url}
        except requests.RequestException as exc:
            logger.warning("go2rtc offline/inacessível: %s", exc)
            return {"online": False, "api_base_url": self.base_url, "error": str(exc)}

    def get_active_streams(self) -> List[Dict[str, Any]]:
        """Lista streams ativos sem derrubar a aplicação em caso de falha."""
        streams_data = self._fetch_streams()
        if not streams_data:
            return []

        active_cameras: List[Dict[str, Any]] = []
        for stream_name, details in streams_data.items():
            urls = self.build_stream_urls(stream_name)
            active_cameras.append(
                {
                    "name": stream_name,
                    "producers": details.get("producers", []),
                    "consumers": details.get("consumers", []),
                    "rtsp_url": urls["rtsp_url"],
                    "webrtc_url": urls["webrtc_url"],
                    "api_streams_url": urls["api_streams_url"],
                }
            )

        logger.info("go2rtc retornou %s stream(s) ativo(s)", len(active_cameras))
        return active_cameras

    def get_streams_index(self) -> Dict[str, Dict[str, Any]]:
        return self._fetch_streams() or {}


    def get_streams_snapshot(self) -> Dict[str, Any]:
        streams = self._fetch_streams()
        if streams is None:
            return {"online": False, "streams": {}}
        return {"online": True, "streams": streams}

    def build_stream_urls(self, stream_name: str) -> Dict[str, str]:
        safe_name = stream_name.strip()
        return {
            "rtsp_url": f"rtsp://{self.rtsp_host}:{self.rtsp_port}/{safe_name}",
            "api_streams_url": f"{self.base_url}/api/streams",
            "webrtc_url": f"ws://{self.webrtc_host}:{self.webrtc_port}/api/ws?src={safe_name}",
        }

    def _fetch_streams(self) -> Optional[Dict[str, Dict[str, Any]]]:
        try:
            response = requests.get(f"{self.base_url}/api/streams", timeout=5)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                logger.warning("Resposta inesperada do go2rtc /api/streams: %s", type(payload).__name__)
                return {}
            return payload
        except requests.RequestException as exc:
            logger.warning("Falha ao listar streams no go2rtc: %s", exc)
            return None
