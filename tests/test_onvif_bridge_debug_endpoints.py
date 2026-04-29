import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import onvif_bridge.main as bridge_main


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
