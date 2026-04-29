"""ONVIF Bridge isolado para compatibilidade DVR via IP virtual."""

from .config import BridgeConfig, BridgeDevice, load_config

__all__ = ["BridgeConfig", "BridgeDevice", "load_config"]
