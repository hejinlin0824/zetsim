"""Schematic — 原理图网表：把用户画的电路（元件+连线）变成仿真引擎的实时接线。

数据格式（与前端画布一致）:
  {"components": [{"id","type","x","y","props":{...}}],
   "wires": [{"a": [comp_id, pin], "b": [comp_id, pin]}]}

构建过程:
  1. 连线 -> union-find 分组 -> 电气网络(net)
  2. MCU 引脚所在网络绑定到 board 的对应引脚 Net
  3. LED/按键/电位器生成器件对象（数字语义），接到网络
  4. 若存在 R/C/VCC/串阻 LED -> 重建 mini-SPICE 电路（结点电压/LED 电流可解）
  5. 探针 -> 记录网络电压轨迹（示波器通道）
"""
from __future__ import annotations
from .board import Board
from .devices import Led, Button, Potentiometer
from .spice import CoupledCircuit

# 元件类型定义: 引脚名列表
PIN_DEFS = {
    "mcu": [f"PA{i}" for i in range(16)] + ["PB0", "PB1"],
    "led": ["A", "K"],
    "resistor": ["1", "2"],
    "capacitor": ["1", "2"],
    "button": ["1", "2"],
    "pot": ["W", "B"],
    "gnd": ["G"],
    "vcc": ["V"],
    "probe": ["P"],
}

ANALOG_TYPES = {"resistor", "capacitor", "vcc"}     # 触发 SPICE 参与的元件


class _UF:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


class Probe:
    """示波器探针：记录网络电压轨迹（SPICE 结点电压优先，数字网回退电平）。"""

    def __init__(self, comp_id: str, sch_ref, net_id: str, color_idx: int):
        self.id = comp_id
        self.sch = sch_ref
        self.net_id = net_id
        self.color_idx = color_idx
        self.trace: list[tuple[int, float]] = []
        self._installed_net = None

    def _voltage(self) -> float:
        return self.sch.net_voltage(self.net_id)

    def sample(self, now_ns: int):
        net = self.sch._net_of(self.net_id)
        if net is not None and self._installed_net is not net:
            self._installed_net = net      # 重建后重新挂钩
        if not self.trace:
            self.trace.append((now_ns, self._voltage()))
        elif now_ns - self.trace[-1][0] >= 20_000:
            self.trace.append((now_ns, self._voltage()))
        self.trace = self.trace[-3000:]


class Schematic:
    """绑定到 Board 的原理图状态。apply() 后即可仿真。"""

    def __init__(self, board: Board):
        self.board = board
        self.data: dict = {"components": [], "wires": []}
        self.components: dict[str, dict] = {}
        self.nets: dict[str, list[tuple[str, str]]] = {}   # net_id -> [pin refs]
        self.pin_net: dict[tuple[str, str], str] = {}
        self.mcu_pin_nets: dict[str, str] = {}             # "PA5" -> net_id
        self.leds: dict[str, Led] = {}
        self.buttons: dict[str, Button] = {}
        self.pots: dict[str, Potentiometer] = {}
        self.probes: dict[str, Probe] = {}
        self.button_states: dict[str, bool] = {}
        self.pot_values: dict[str, float] = {}
        self.spice: CoupledCircuit | None = None
        self._spice_leds: dict[str, object] = {}           # led id -> Diode
        self._node_of_net: dict[str, str] = {}

    # ---------------- 对外 ----------------
    def apply(self, data: dict):
        self.data = data
        self._extract()
        self._bind()

    def net_voltage(self, net_id: str) -> float:
        nid = self._node_of_net.get(net_id)
        if self.spice and nid:
            return self.spice.circuit.voltage(nid)
        net = self._net_of(net_id)
        if net is None:
            return 0.0
        v = net.voltage()
        return v if v is not None else (3.3 if net.level == 1 else 0.0)

    # ---------------- 器件交互 ----------------
    def press(self, comp_id: str, down: bool):
        btn = self.buttons.get(comp_id)
        if btn and down and btn.pressed:
            btn.release()          # 上一轮 release 丢失（页面失焦等）：先复位再按，保证有上升沿
        self.button_states[comp_id] = down
        if btn:
            (btn.press if down else btn.release)()
        self._rebuild_spice()

    def set_pot(self, comp_id: str, volts: float):
        self.pot_values[comp_id] = max(0.0, min(3.3, volts))
        pot = self.pots.get(comp_id)
        if pot:
            pot.set(self.pot_values[comp_id])
        self._rebuild_spice()

    # ---------------- 网表提取 ----------------
    def _extract(self):
        self.components = {c["id"]: c for c in self.data.get("components", [])}
        uf = _UF()
        for cid, comp in self.components.items():
            for p in PIN_DEFS.get(comp["type"], []):
                uf.find((cid, p))
        for w in self.data.get("wires", []):
            a, b = tuple(w["a"]), tuple(w["b"])
            if a in uf.parent and b in uf.parent:
                uf.union(a, b)
        self.pin_net = {pin: uf.find(pin) for pin in uf.parent}
        groups: dict[str, list] = {}
        for pin, root in self.pin_net.items():
            groups.setdefault(root, []).append(pin)
        self.nets = groups
        # MCU 引脚 -> 网络
        self.mcu_pin_nets = {}
        for (cid, pin), root in self.pin_net.items():
            if self.components[cid]["type"] == "mcu":
                self.mcu_pin_nets[pin] = root

    # ---------------- 接线 ----------------
    def _net_of(self, net_id: str):
        """网络对应的最合适驱动 Net（优先 MCU 引脚 Net）。"""
        best = None
        for cid, pin in self.nets.get(net_id, []):
            comp = self.components.get(cid)
            if comp is None:
                continue
            if comp["type"] == "mcu" and pin.startswith("P"):
                port_idx = "ABCDE".index(pin[1])
                return self.board.net(port_idx, int(pin[2:]))
            best = best or self._synth_net(net_id)
        return best

    def _synth_net(self, net_id: str):
        return self.board.schematic_net(net_id)

    def _bind(self):
        board = self.board
        # 1) 清掉旧绑定（保留 EXTI 板级 watcher）
        for n in board.nets.values():
            n.reset_bindings()
        board.schematic_nets.clear()
        self.leds.clear()
        self.buttons.clear()
        self.pots.clear()
        # 2) 生成器件并接网络
        for cid, comp in self.components.items():
            t = comp["type"]
            props = comp.get("props", {})
            if t == "led":
                net = self._net_of(self.pin_net[(cid, "A")])
                if net is not None:
                    led = Led(board, cid, net, color=props.get("color", "red"))
                    self.leds[cid] = led
            elif t == "button":
                net = self._net_of(self.pin_net[(cid, "1")])
                if net is not None:
                    btn = Button(board, cid, net)
                    btn.pressed = self.button_states.get(cid, False)
                    if btn.pressed:
                        btn.press()
                    self.buttons[cid] = btn
            elif t == "pot":
                net = self._net_of(self.pin_net[(cid, "W")])
                if net is not None:
                    v = self.pot_values.get(cid, 1.65)
                    self.pots[cid] = Potentiometer(board, cid, net, volts=v)
        # 3) 探针
        colors = 0
        for cid, comp in self.components.items():
            if comp["type"] == "probe":
                net_id = self.pin_net.get((cid, "P"))
                if net_id is not None:
                    nid = net_id
                    p = Probe(cid, self, nid, colors)
                    colors += 1
                    self.probes[cid] = p
        # 4) SPICE
        self._rebuild_spice()

    # ---------------- SPICE 重建 ----------------
    def _rebuild_spice(self):
        board = self.board
        need = any(c["type"] in ANALOG_TYPES for c in self.components.values())
        if not need:
            self.spice = None
            self._spice_leds.clear()
            self._node_of_net = {}
            board.devices.pop("spice", None)
            return
        cc = CoupledCircuit(board, dt_ns=5_000)
        self.spice = cc
        board.devices["spice"] = cc
        # 网络名 -> 节点名；含 GND 元件的网络为参考地
        self._node_of_net = {}
        ground_roots = set()
        for cid, comp in self.components.items():
            if comp["type"] == "gnd":
                ground_roots.add(self.pin_net[(cid, "G")])
        for root in self.nets:
            self._node_of_net[root] = "GND" if root in ground_roots else f"n{root[:12]}"
        # MCU 引脚 / VCC -> 电压源
        for cid, comp in self.components.items():
            if comp["type"] == "mcu":
                for pin, root in self.mcu_pin_nets.items():
                    if self._node_of_net.get(root) not in (None, "GND"):
                        cc.attach_pin(pin, self._node_of_net[root])
            elif comp["type"] == "vcc":
                root = self.pin_net[(cid, "V")]
                node = self._node_of_net.get(root)
                if node and node != "GND":
                    src = cc.circuit.add_source(node, "GND")
                    src.volts = 3.3
        # R / C / LED
        for cid, comp in self.components.items():
            props = comp.get("props", {})
            t = comp["type"]
            if t == "resistor":
                na, nb = self._two_nodes(cid)
                if na and nb:
                    cc.circuit.add_r(na, nb, float(props.get("ohms", 1000)))
            elif t == "capacitor":
                na, nb = self._two_nodes(cid)
                if na and nb:
                    cc.circuit.add_c(na, nb, float(props.get("farads", 100e-9)))
            elif t == "led":
                na, nb = self._two_nodes(cid)
                if na and nb:
                    d = cc.circuit.add_led(na, nb, is_=1e-16, n_vt=0.08)
                    self._spice_leds[cid] = d
            elif t == "button":
                # 按下 = 10Ω 接通，松开 = 10MΩ（数字驱动之外补充模拟路径）
                na, nb = self._two_nodes(cid)
                if na and nb:
                    cc.circuit.add_r(na, nb, 10.0 if self.button_states.get(cid) else 10e6)

    def _two_nodes(self, cid):
        comp = self.components[cid]
        pins = PIN_DEFS[comp["type"]]
        na = self._node_of_net.get(self.pin_net.get((cid, pins[0])))
        nb = self._node_of_net.get(self.pin_net.get((cid, pins[1])))
        return na, nb

    # ---------------- 运行期（引擎经 board.devices 每片调用）----------------
    def sample(self, now_ns: int):
        for p in self.probes.values():
            p.sample(now_ns)

    def led_states(self) -> dict:
        """LED 运行态: on/brightness（SPICE 电流优先，否则数字电平）。"""
        out = {}
        for cid, led in self.leds.items():
            on = led.on
            bright = 1.0 if on else 0.0
            d = self._spice_leds.get(cid)
            if d is not None and self.spice is not None:
                i = abs(d.i_last)
                on = i > 1e-3
                bright = max(0.0, min(1.0, i / 0.015))
            out[cid] = {"on": on, "brightness": round(bright, 3),
                        "color": led.color}
        return out

    def snapshot(self) -> dict:
        return {
            "leds": self.led_states(),
            "buttons": {cid: b.pressed for cid, b in self.buttons.items()},
            "pots": {cid: p.volts for cid, p in self.pots.items()},
            "probes": {cid: [[round(t / 1e6, 4), round(v, 3)] for t, v in p.trace[-300:]]
                       for cid, p in self.probes.items()},
        }
