"""zetsim Web 仪表盘 — 原理图画布版（M8）。

启动:  python -m zetsim serve   页面: http://127.0.0.1:8000
"""
from __future__ import annotations
import base64
import json
import threading
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from .board import Board
from .engine import Simulation
from .devices import Ssd1306
from .schematic import Schematic
from .build import build_project, PROJECT_FILES

# 首次打开的默认示例电路：MCU + LED(PA5) + 按键(PA0) + 电位器(PA1) + 探针
DEFAULT_SCHEMATIC = {
    "components": [
        {"id": "MCU", "type": "mcu", "x": 60, "y": 60, "props": {}},
        {"id": "LED1", "type": "led", "x": 400, "y": 200, "props": {"color": "red"}},
        {"id": "SW1", "type": "button", "x": 400, "y": 420, "props": {}},
        {"id": "POT1", "type": "pot", "x": 400, "y": 520, "props": {}},
        {"id": "GND1", "type": "gnd", "x": 560, "y": 260, "props": {}},
        {"id": "GND2", "type": "gnd", "x": 560, "y": 470, "props": {}},
        {"id": "GND3", "type": "gnd", "x": 560, "y": 560, "props": {}},
        {"id": "PR1", "type": "probe", "x": 350, "y": 300, "props": {}},
    ],
    "wires": [
        {"a": ["MCU", "PA5"], "b": ["LED1", "A"]},
        {"a": ["LED1", "K"], "b": ["GND1", "G"]},
        {"a": ["MCU", "PA0"], "b": ["SW1", "1"]},
        {"a": ["SW1", "2"], "b": ["GND2", "G"]},
        {"a": ["MCU", "PA1"], "b": ["POT1", "W"]},
        {"a": ["POT1", "B"], "b": ["GND3", "G"]},
        {"a": ["MCU", "PA5"], "b": ["PR1", "P"]},
    ],
}


def _led8_schematic() -> dict:
    """8-LED 跑马灯预设电路：PA0..PA7 → LED1..LED8 → GND。"""
    comps = [{"id": "MCU", "type": "mcu", "x": 60, "y": 60, "props": {}}]
    wires = []
    for i in range(8):
        y = 70 + i * 60
        comps.append({"id": f"LED{i+1}", "type": "led", "x": 470, "y": y,
                      "props": {"color": "red" if i % 2 == 0 else "green"}})
        comps.append({"id": f"GND{i+1}", "type": "gnd", "x": 650, "y": y + 22, "props": {}})  # 与 LED 阴极同高→直线
        wires.append({"a": ["MCU", f"PA{i}"], "b": [f"LED{i+1}", "A"]})
        wires.append({"a": [f"LED{i+1}", "K"], "b": [f"GND{i+1}", "G"]})
    return {"components": comps, "wires": wires}


PRESET_SCHEMATICS = {
    "default": DEFAULT_SCHEMATIC,
    "led8_marquee": _led8_schematic(),
}


class Dashboard:
    """Board + 原理图 + 仿真线程。"""

    def __init__(self, firmware: str | None = None):
        self.board = Board()
        self.board.reset()
        self.sch = Schematic(self.board)
        self.board.devices["schematic"] = self.sch     # 引擎每片调用 tick()
        oled = Ssd1306(self.board, "oled1")
        self.board.devices["oled1"] = oled
        self.board.i2cs[1].devices[0x3C] = oled        # OLED 固定挂 I2C1
        self.sch.apply(DEFAULT_SCHEMATIC)
        self.sim = Simulation(self.board)
        self.sim.max_slice_ns = 50_000
        self.lock = threading.Lock()
        self.running = False
        self.realtime = True            # 仿真时间与真实时间对齐
        self.firmware_path: str | None = None
        self.uart_text = bytearray()
        self.board.events.subscribe("usart1.tx", lambda e: self.uart_text.append(e.data))
        self._clients: list[WebSocket] = []
        self._loop = None
        self._sim_thread = None       # 仿真线程句柄（死线程可复活）
        self._gen = 0                 # 代数：load 后老线程凭它自杀
        self._anchor = False          # 重新锚定实时节奏（load/reset 后）
        if firmware:
            self.load(firmware)

    # ---------------- 固件与控制 ----------------
    def load(self, path: str):
        with self.lock:
            self.running = False
            self.board.reset()
            self.board.core.load_file(path)
            self.firmware_path = path
            self.uart_text.clear()
            self.sim.halted = False
            self.sim.halt_reason = None
            self.sim._ext.clear()
            self._anchor = True        # 重置后墙钟锚点必须重算，否则全速追赶
            self.broadcast({"type": "loaded", "path": path})
        self.start()                   # 换固件即开跑

    def _run_loop(self, wall0=None, sim0=None, gen=None):
        last_push = 0.0
        wall0 = wall0 if wall0 is not None else time.time()
        sim0 = sim0 if sim0 is not None else self.sim.now
        gen = gen if gen is not None else self._gen
        while self.running and gen == self._gen:
            try:
                t0 = time.time()
                if self._anchor:       # load/reset 后重锚，防止时间倒流引发全速追赶
                    wall0, sim0 = time.time(), self.sim.now
                    self._anchor = False
                with self.lock:
                    self.sim.run(until_ms=5, wall_timeout_s=2)
                # 实时节奏：仿真时间对齐墙钟（忙等固件跟不上时不等待）
                if self.realtime:
                    ahead = (self.sim.now - sim0) / 1e9 - (time.time() - wall0)
                    if ahead > 0.002:
                        time.sleep(min(ahead, 0.1))
                elif time.time() - t0 > 0.05:
                    time.sleep(0.001)
                if time.time() - last_push > 0.12:
                    last_push = time.time()
                    self.push_state()
            except Exception as e:      # 单片异常绝不杀死推送循环
                print(f"[zetsim] 仿真循环异常: {e!r}", flush=True)
                time.sleep(0.05)

    def start(self):
        self.running = True
        if self._sim_thread is None or not self._sim_thread.is_alive():
            self._gen += 1
            self._anchor = True
            self._sim_thread = threading.Thread(
                target=self._run_loop, args=(None, None, self._gen), daemon=True)
            self._sim_thread.start()

    def ensure_thread(self):
        """交互（按键/电位器）到达时若线程已死则复活——用户没主动暂停就应有反应。"""
        if self.running:
            self.start()

    def pause(self):
        self.running = False

    def reset(self):
        self.pause()
        time.sleep(0.05)
        if self.firmware_path:
            self.load(self.firmware_path)

    # ---------------- 前端通信 ----------------
    async def register(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        import asyncio
        self._loop = asyncio.get_running_loop()

    def unregister(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    def broadcast(self, msg: dict):
        import asyncio
        loop = getattr(self, "_loop", None)
        if loop is None or not self._clients:
            return
        try:
            data = json.dumps(msg)
            asyncio.run_coroutine_threadsafe(self._send_all(data), loop)
        except Exception:
            pass

    async def _send_all(self, data: str):
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister(ws)

    def push_state(self):
        self.broadcast(self.state())

    def state(self) -> dict:
        b = self.board
        oled = b.devices.get("oled1")
        oled_b64 = None
        if oled:
            oled_b64 = base64.b64encode(bytes(oled.fb)).decode()
        st = {
            "type": "state",
            "t_ms": round(self.sim.now / 1e6, 3),
            "running": self.running,
            "sim_halted": self.sim.halted,
            "halt_reason": self.sim.halt_reason,
            "firmware": self.firmware_path,
            "uart": self.uart_text.decode("utf-8", "replace")[-4000:],
            "oled": oled_b64,
        }
        st.update(self.sch.snapshot())
        return st


def build_app(firmware: str | None = None) -> FastAPI:
    dash = Dashboard(firmware)
    if firmware:
        dash.start()          # 带固件启动即自动开跑
    app = FastAPI(title="zetsim")
    static_dir = Path(__file__).parent / "static"

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/state")
    async def state():
        return JSONResponse(dash.state())

    @app.get("/api/schematic/default")
    async def schematic_default():
        return JSONResponse(DEFAULT_SCHEMATIC)

    @app.get("/api/schematic/preset/{name}")
    async def schematic_preset(name: str):
        preset = PRESET_SCHEMATICS.get(name)
        if preset is None:
            return JSONResponse({"ok": False, "error": f"无此预设 {name}"}, status_code=404)
        with dash.lock:
            dash.sch.apply(preset)
        return JSONResponse({"ok": True, "schematic": preset, "snapshot": dash.sch.snapshot()})

    # ---------- 项目（C 代码编辑 + 编译） ----------
    import re
    _PROJ_NAME = re.compile(r"^[A-Za-z0-9_\-]+$")

    def _proj_dir(name: str) -> Path:
        if not _PROJ_NAME.match(name):
            raise ValueError("项目名只能字母数字_-")
        return Path.cwd() / "projects" / name

    @app.get("/api/projects")
    async def projects():
        root = Path.cwd() / "projects"
        items = sorted(d.name for d in root.iterdir()
                       if d.is_dir() and (d / "main.c").exists()) if root.exists() else []
        return {"items": items}

    @app.post("/api/projects")
    async def project_create(body: dict):
        import re, shutil
        name = str(body.get("name", "")).strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*$", name):
            return JSONResponse({"ok": False, "error": "项目名：字母开头，只用字母数字_-"}, status_code=400)
        root = Path.cwd() / "projects"
        dst = root / name
        if dst.exists():
            return JSONResponse({"ok": False, "error": f"项目 {name} 已存在"}, status_code=400)
        src = root / "led_marquee"
        if not (src / "main.c").exists():
            return JSONResponse({"ok": False, "error": "模板 led_marquee 缺失"}, status_code=400)
        dst.mkdir(parents=True)
        for f in PROJECT_FILES:
            if (src / f).exists():
                shutil.copy(src / f, dst / f)
        return {"ok": True, "name": name}

    @app.delete("/api/project/{name}")
    async def project_delete(name: str):
        import shutil
        try:
            pdir = _proj_dir(name)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        if not (pdir / "main.c").exists():
            return JSONResponse({"ok": False, "error": "项目不存在"}, status_code=404)
        shutil.rmtree(pdir)
        return {"ok": True}

    @app.get("/api/project/{name}")
    async def project_get(name: str):
        try:
            pdir = _proj_dir(name)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        files: dict[str, str] = {}
        order = {"main.c": 0, "startup.c": 1}
        paths = sorted(pdir.glob("*.c"), key=lambda p: order.get(p.name, 2))
        paths += sorted(pdir.glob("*.h"))
        if (pdir / "link.ld").exists():
            paths.append(pdir / "link.ld")
        for path in paths:
            files[path.name] = path.read_text(encoding="utf-8")
        if not files:
            return JSONResponse({"ok": False, "error": "项目不存在"}, status_code=404)
        return {"ok": True, "files": files}

    @app.post("/api/project/{name}/file")
    async def file_create(name: str, body: dict):
        import re
        fname = str(body.get("name", "")).strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*\.(c|h)$", fname):
            return JSONResponse({"ok": False, "error": "文件名：字母开头，扩展名 .c 或 .h"}, status_code=400)
        try:
            pdir = _proj_dir(name)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        if (pdir / fname).exists():
            return JSONResponse({"ok": False, "error": f"{fname} 已存在"}, status_code=400)
        content = str(body.get("content", "")) or (
            f"/* {fname} */\n" if fname.endswith(".h") else
            f"/* {fname}：新源文件，函数在 main.c 里声明后调用 */\n")
        (pdir / fname).write_text(content, encoding="utf-8")
        return {"ok": True}

    @app.delete("/api/project/{name}/file/{fname}")
    async def file_delete(name: str, fname: str):
        from .build import PROTECTED
        if fname in PROTECTED:
            return JSONResponse({"ok": False, "error": f"{fname} 是必需文件，不能删"}, status_code=400)
        try:
            pdir = _proj_dir(name)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        target = pdir / fname
        if not target.exists():
            return JSONResponse({"ok": False, "error": "文件不存在"}, status_code=404)
        target.unlink()
        return {"ok": True}

    @app.post("/api/project/{name}")
    async def project_save(name: str, body: dict):
        import re
        try:
            pdir = _proj_dir(name)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        files = body.get("files", {})
        for fname, content in files.items():
            ok_name = fname in PROJECT_FILES or re.match(r"^[A-Za-z][A-Za-z0-9_\-]*\.(c|h)$", fname)
            if not ok_name:
                return JSONResponse({"ok": False, "error": f"不允许写 {fname}"}, status_code=400)
            (pdir / fname).write_text(str(content), encoding="utf-8")
        return {"ok": True}

    @app.post("/api/project/{name}/build")
    async def project_build(name: str):
        try:
            pdir = _proj_dir(name)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        ok, log = build_project(pdir)
        if not ok:
            return {"ok": False, "log": log}
        hex_path = pdir / "firmware.hex"
        try:
            dash.load(str(hex_path))
        except Exception as e:
            return {"ok": False, "log": log + f"\n加载固件失败: {e}"}
        return {"ok": True, "log": log, "firmware": str(hex_path)}

    @app.post("/api/schematic")
    async def schematic_set(body: dict):
        try:
            with dash.lock:
                dash.sch.apply(body)
            return {"ok": True, "snapshot": dash.sch.snapshot()}
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    @app.post("/api/load")
    async def load(body: dict):
        path = str(body.get("path", ""))
        try:
            dash.load(path)
            return {"ok": True}
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    @app.post("/api/control/{action}")
    async def control(action: str):
        if action == "run":
            dash.start()
        elif action == "pause":
            dash.pause()
        elif action == "reset":
            dash.reset()
        else:
            return JSONResponse({"ok": False}, status_code=404)
        return {"ok": True, "running": dash.running}

    @app.post("/api/comp/{cid}/{action}")
    async def comp(cid: str, action: str, body: dict | None = None):
        body = body or {}
        if action == "press":
            dash.sch.press(cid, True)
        elif action == "release":
            dash.sch.press(cid, False)
        elif action == "pot":
            dash.sch.set_pot(cid, float(body.get("volts", 1.65)))
        else:
            return JSONResponse({"ok": False}, status_code=404)
        dash.ensure_thread()
        return {"ok": True}

    @app.post("/api/uart-rx")
    async def uart_rx(body: dict):
        with dash.lock:
            for ch in str(body.get("text", "")).encode("utf-8", "replace"):
                dash.board.usarts[1].inject_rx(ch)
        return {"ok": True}

    @app.get("/api/firmwares")
    async def firmwares():
        fw_dir = Path.cwd() / "firmware"
        items = []
        if fw_dir.exists():
            items = [f.name for f in sorted(fw_dir.glob("*.hex"))]
        return {"items": items}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await dash.register(ws)
        try:
            while True:
                msg = await ws.receive_text()
                data = json.loads(msg)
                kind = data.get("type")
                if kind == "comp":
                    if data["action"] == "pot":
                        dash.sch.set_pot(data["cid"], float(data["value"]))
                    else:
                        dash.sch.press(data["cid"], data["action"] == "press")
                    dash.ensure_thread()
        except WebSocketDisconnect:
            dash.unregister(ws)

    return app


def serve(host="127.0.0.1", port=8000, firmware=None):
    import uvicorn
    app = build_app(firmware)
    print(f"zetsim 原理图仪表盘: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
