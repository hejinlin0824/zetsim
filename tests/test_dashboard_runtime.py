"""Integration regression tests for the threaded web dashboard simulation loop."""
from __future__ import annotations

import time
from pathlib import Path

from zetsim.webapp import Dashboard

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_thread_keeps_blink_firmware_edges_live() -> None:
    """Repeated short dashboard slices must not starve SysTick-driven LED updates."""
    firmware = ROOT / "firmware" / "blink.hex"
    dashboard = Dashboard()
    dashboard.load(str(firmware))

    observed = []
    started = time.monotonic()
    deadline = started + 3.2
    try:
        while time.monotonic() < deadline:
            state = dashboard.state()
            led = state.get("leds", {}).get("LED1", {}).get("on")
            if led is not None and (not observed or led != observed[-1]):
                observed.append(led)
            time.sleep(0.015)
    finally:
        dashboard.pause()
        if dashboard._sim_thread is not None:
            dashboard._sim_thread.join(timeout=1.0)

    elapsed = time.monotonic() - started
    final_state = dashboard.state()
    assert final_state["t_ms"] >= 1500, (
        f"dashboard simulation advanced too slowly: t={final_state['t_ms']} ms "
        f"over {elapsed:.2f} wall seconds"
    )
    assert len(observed) >= 6, (
        f"expected regular LED state changes from blink.hex; observed {len(observed)} "
        f"distinct states {observed} over {elapsed:.2f} wall seconds"
    )
