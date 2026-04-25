"""Configurações globais e variáveis de ambiente do Gateway."""

import os

CAMERA_REGISTRY_PATH: str = os.getenv("CAMERA_REGISTRY_PATH", "data/camera_registry.json")

GO2RTC_API_BASE_URL: str = os.getenv("GO2RTC_API_BASE_URL", "http://localhost:1984")
GO2RTC_RTSP_HOST: str = os.getenv("GO2RTC_RTSP_HOST", "localhost")
GO2RTC_RTSP_PORT: int = int(os.getenv("GO2RTC_RTSP_PORT", "8554"))
GO2RTC_WEBRTC_HOST: str = os.getenv("GO2RTC_WEBRTC_HOST", "localhost")
GO2RTC_WEBRTC_PORT: int = int(os.getenv("GO2RTC_WEBRTC_PORT", "8555"))
