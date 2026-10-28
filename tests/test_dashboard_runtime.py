"""Integration regression tests for the threaded web dashboard simulation loop."""
from __future__ import annotations

import time
from pathlib import Path

from zetsim.webapp import Dashboard

ROOT = Path(__file__).resolve().parents[1]



def test_systick_poll_fast_forward_respects_short_run_deadlines() -> None:
    """A 5ms service slice must not jump straight to a 100ms SysTick expiry."""
    from zetsim.asm import Asm, Firmware
    from zetsim.board import Board
    from zetsim.engine import Simulation

    firmware = Firmware(sp=0x20005000, reset=0x08000100)
    asm = Asm(0x08000100)
    asm.mov32(0, 0xE000E010)       # SysTick base
    asm.mov32(1, 800_000 - 1)      # 100ms @ 8MHz
    asm.str(1, 0, 4)               # LOAD
    asm.movs(1, 0)
    asm.str(1, 0, 8)               # VAL
    asm.movs(1, 5)
    asm.str(1, 0, 0)               # ENABLE | CLKSOURCE
    asm.label("poll")
    asm.ldr(1, 0, 0)               # tight CTRL polling loop
    asm.bw("poll")
    firmware.add(0x08000100, asm.assemble())

    board = Board()
    board.reset()
    board.core.load_segments(firmware.build())
    sim = Simulation(board, max_slice_ns=50_000)

    for _ in range(8):
        before = sim.now
        sim.run(until_ms=5, wall_timeout_s=1)
        elapsed = sim.now - before
        assert elapsed <= 5_100_000, (
            f"5ms slice advanced {elapsed / 1e6:.3f}ms; event fast-forward "
            "must respect until_ms so coupled devices keep advancing per slice"
        )

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
