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
import math
from .board import Board
from .devices import Led, Button, Potentiometer
from .spice import CoupledCircuit

# 元件类型定义: 引脚名列表
PIN_DEFS = {
    "mcu": [f"P{p}{i}" for p in "ABCDE" for i in range(16)] + ["VDD", "VSS"],
    "led": ["A", "K"],
    "resistor": ["1", "2"],
    "capacitor": ["1", "2"],
    "button": ["1", "2"],
    "pot": ["W", "B"],
    "gnd": ["G"],
    "vcc": ["V"],
    "probe": ["P"],
}

ANALOG_TYPES = {"resistor", "capacitor"}     # 只有真实模拟元件才触发 SPICE（VCC 走网表电源判定，不拖慢仿真）


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
        self.board.devices["schematic"] = self
        self.data: dict = {"components": [], "wires": []}
        self.components: dict[str, dict] = {}
        self.nets: dict[str, list[tuple[str, str]]] = {}   # net_id -> [pin refs]
        self.pin_net: dict[tuple[str, str], str] = {}
        self.mcu_pin_nets: dict[str, str] = {}             # "PA5" -> net_id
        self.leds: dict[str, Led] = {}
        self.buttons: dict[str, Button] = {}
        self._grounded: set = set()      # 接了 GND 符号的网络（LED 回路判定）
        self._powered_nets: set = set()  # 接了 VCC 符号的网络
        self.mcu_powered = True          # VDD/VSS 都接好才 True
        self.pots: dict[str, Potentiometer] = {}
        self.probes: dict[str, Probe] = {}
        self.button_states: dict[str, bool] = {}
        self.button_pending: dict[str, tuple[bool, int]] = {}  # (期望状态, 开始稳定的仿真时刻)
        self.pot_values: dict[str, float] = {}
        self.spice: CoupledCircuit | None = None
        self._spice_leds: dict[str, object] = {}           # led id -> Diode
        self._spice_buttons: dict[str, object] = {}        # button id -> live Resistor
        self._spice_pots: dict[str, object] = {}           # pot id -> live VoltageSource
        self._node_of_net: dict[str, str] = {}

    @staticmethod
    def _validated_data(data: dict) -> dict:
        """校验整个画布快照，再允许它影响正在运行的电路。"""
        if not isinstance(data, dict):
            raise ValueError("原理图必须是对象")
        raw_components = data.get("components", [])
        raw_wires = data.get("wires", [])
        if not isinstance(raw_components, list) or not isinstance(raw_wires, list):
            raise ValueError("components 和 wires 必须是数组")

        components = []
        by_id: dict[str, dict] = {}
        mcu_count = 0
        for index, raw in enumerate(raw_components):
            if not isinstance(raw, dict):
                raise ValueError(f"元件 #{index + 1} 必须是对象")
            cid, kind = raw.get("id"), raw.get("type")
            if not isinstance(cid, str) or not cid.strip() or cid != cid.strip():
                raise ValueError(f"元件 #{index + 1} 的 id 无效")
            if cid in by_id:
                raise ValueError(f"元件 id 重复：{cid}")
            if kind not in PIN_DEFS:
                raise ValueError(f"元件 {cid} 的类型不支持：{kind}")
            if kind == "mcu":
                mcu_count += 1
                if mcu_count > 1:
                    raise ValueError("一个原理图只能放置一个 STM32 MCU")
            props = raw.get("props", {})
            if not isinstance(props, dict):
                raise ValueError(f"元件 {cid} 的 props 必须是对象")
            comp = dict(raw)
            comp["id"], comp["type"] = cid, kind
            comp["props"] = dict(props)
            for coord in ("x", "y"):
                try:
                    value = float(raw.get(coord, 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"元件 {cid} 的 {coord} 坐标无效") from exc
                if not math.isfinite(value):
                    raise ValueError(f"元件 {cid} 的 {coord} 坐标必须是有限数")
                comp[coord] = value
            for prop, default, label in (("ohms", 1000.0, "电阻"), ("farads", 100e-9, "电容")):
                if (kind == "resistor" and prop == "ohms") or (kind == "capacitor" and prop == "farads"):
                    try:
                        value = float(comp["props"].get(prop, default))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"元件 {cid} 的{label}值无效") from exc
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError(f"元件 {cid} 的{label}值必须是有限正数")
                    comp["props"][prop] = value
            if kind == "button":
                try:
                    debounce_ms = float(comp["props"].get("debounce_ms", 0.0))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"元件 {cid} 的消抖时间无效") from exc
                if not math.isfinite(debounce_ms) or not 0.0 <= debounce_ms <= 1000.0:
                    raise ValueError(f"元件 {cid} 的消抖时间必须在 0 到 1000 ms 之间")
                comp["props"]["debounce_ms"] = debounce_ms
            components.append(comp)
            by_id[cid] = comp

        wires = []
        for index, raw in enumerate(raw_wires):
            if not isinstance(raw, dict):
                raise ValueError(f"连线 #{index + 1} 必须是对象")
            endpoints = []
            for field in ("a", "b"):
                endpoint = raw.get(field)
                if not isinstance(endpoint, (list, tuple)) or len(endpoint) != 2:
                    raise ValueError(f"连线 #{index + 1} 的 {field} 端点格式无效")
                cid, pin = endpoint
                if not isinstance(cid, str) or cid not in by_id:
                    raise ValueError(f"连线 #{index + 1} 引用了不存在的元件：{cid}")
                if not isinstance(pin, str) or pin not in PIN_DEFS[by_id[cid]["type"]]:
                    raise ValueError(f"元件 {cid} 不存在引脚 {pin}")
                endpoints.append([cid, pin])
            wire = dict(raw)
            wire["a"], wire["b"] = endpoints
            wires.append(wire)

        normalized = dict(data)
        normalized["components"], normalized["wires"] = components, wires
        return normalized

    # ---------------- 对外 ----------------
    def apply(self, data: dict):
        candidate = self._validated_data(data)
        previous = self.data
        self.data = candidate
        active_buttons = {item["id"] for item in candidate["components"] if item["type"] == "button"}
        active_pots = {item["id"] for item in candidate["components"] if item["type"] == "pot"}
        self.button_states = {k: v for k, v in self.button_states.items() if k in active_buttons}
        self.button_pending = {k: v for k, v in self.button_pending.items() if k in active_buttons}
        self.pot_values = {k: v for k, v in self.pot_values.items() if k in active_pots}
        try:
            self._extract()
            self._bind()
        except Exception:
            # 构建意外失败时回到上一个可运行快照，而不是留下半更新的网表。
            self.data = previous
            self._extract()
            self._bind()
            raise

    def net_voltage(self, net_id: str) -> float:
        nid = self._node_of_net.get(net_id)
        if self.spice and self.spice.stepped and nid and nid in self.spice.circuit.nodes:
            return self.spice.circuit.voltage(nid)
        # 孤立探针/尚未步进的模拟节点回退到数字 Net，不能因缺失节点杀死仿真线程。
        net = self._net_of(net_id)
        if net is None:
            return 0.0
        v = net.voltage()
        return v if v is not None else (3.3 if net.level == 1 else 0.0)

    def mcu_pin_voltage(self, pin: str) -> float | None:
        """返回 MCU 引脚已求解的模拟电压（优先 SPICE 结点，否则取数字/器件网络电压）。"""
        root = self.mcu_pin_nets.get(pin)
        node = self._node_of_net.get(root) if root is not None else None
        if (self.spice is not None and self.spice.stepped and node
                and node in self.spice.circuit.nodes):
            return self.spice.circuit.voltage(node)
        if root is not None:
            net = self._net_of(root)
            if net is not None:
                return net.voltage()
        return None

    # ---------------- 器件交互 ----------------
    def _apply_button_state(self, comp_id: str, down: bool, *, force_retrigger: bool = False) -> bool:
        btn = self.buttons.get(comp_id)
        if btn is None:
            return False
        down = bool(down)
        if down == btn.pressed:
            self.button_states[comp_id] = down
            return True
        if force_retrigger and down and btn.pressed:
            btn.release()          # 零消抖模式下，修复丢失 release 后的重复按下
        (btn.press if down else btn.release)()
        self.button_states[comp_id] = down
        # 开关电阻随稳定后的接点状态改变；保留 RC/二极管动态历史。
        resistor = self._spice_buttons.get(comp_id)
        if resistor is not None:
            resistor.r = 10.0 if down else 10e6
        return True

    def press(self, comp_id: str, down: bool) -> bool:
        btn = self.buttons.get(comp_id)
        if btn is None:
            return False
        down = bool(down)
        delay_ms = float(self.components.get(comp_id, {}).get("props", {}).get("debounce_ms", 0.0))
        if delay_ms > 0.0:
            self.button_pending[comp_id] = (down, int(self.board.sysctrl.now_ns))
            return True
        self.button_pending.pop(comp_id, None)
        return self._apply_button_state(comp_id, down, force_retrigger=down and btn.pressed)

    def set_pot(self, comp_id: str, volts: float) -> bool:
        pot = self.pots.get(comp_id)
        if pot is None:
            return False
        try:
            value = float(volts)
        except (TypeError, ValueError) as exc:
            raise ValueError("电位器电压必须是数字") from exc
        if not math.isfinite(value):
            raise ValueError("电位器电压必须是有限数")
        value = max(0.0, min(3.3, value))
        self.pot_values[comp_id] = value
        pot.set(value)
        source = self._spice_pots.get(comp_id)
        if source is not None:
            source.volts = value
        # 电位器源通过有限输出阻抗接入 SPICE；不要覆盖共享引脚上的 MCU GPIO 驱动。
        # 不重建求解器，避免 RC 状态归零。
        return True

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
        """网络对应的最合适驱动 Net；同一原理图网络中的 MCU 引脚共享运行时 Net。"""
        best = None
        for cid, pin in self.nets.get(net_id, []):
            comp = self.components.get(cid)
            if comp is None:
                continue
            if comp["type"] == "mcu" and pin.startswith("P") and len(pin) > 2:
                port_idx = "ABCDE".index(pin[1])
                return self.board.resolved_net(port_idx, int(pin[2:]))
            best = best or self._synth_net(net_id)
        return best

    def _synth_net(self, net_id: str):
        return self.board.schematic_net(net_id)

    def _bind(self):
        board = self.board
        # 0) 接地网络集合：所有 GND 符号的 G 引脚所在的网络
        self._grounded = {
            self.pin_net[(c["id"], "G")]
            for c in self.components.values()
            if c["type"] == "gnd" and (c["id"], "G") in self.pin_net
        }
        # 0.5) 电源网络集合（VCC 符号）与 MCU 供电判定：VDD 接 3.3V 且 VSS 接地
        self._powered_nets = {
            self.pin_net[(c["id"], "V")]
            for c in self.components.values()
            if c["type"] == "vcc" and (c["id"], "V") in self.pin_net
        }
        mcu = next((c for c in self.components.values() if c["type"] == "mcu"), None)
        if mcu:
            vdd = self.pin_net.get((mcu["id"], "VDD"))
            vss = self.pin_net.get((mcu["id"], "VSS"))
            self.mcu_powered = vdd in self._powered_nets and vss in self._grounded
            self.board.mcu_power = self.mcu_powered     # 掉电：MCU 引脚全部高阻 + CPU 停跑
        else:
            self.mcu_powered = True
            self.board.mcu_power = True
        # 1) 清掉旧原理图别名与器件绑定（保留每个物理 MCU 引脚的 EXTI watcher）。
        board.clear_schematic_bindings()
        for n in board.nets.values():
            n.reset_bindings()
        board.schematic_nets.clear()
        self.leds.clear()
        self.buttons.clear()
        self.pots.clear()
        self.probes.clear()             # 删除/重建探针时不能残留旧 trace
        self._spice_leds.clear()
        self._spice_buttons.clear()
        self._spice_pots.clear()

        # 2) 将同一 union-find 网络里的 MCU GPIO 物理引脚映射到同一个运行时 Net。
        for root, refs in self.nets.items():
            gpio_refs = [
                (cid, pin) for cid, pin in refs
                if self.components[cid]["type"] == "mcu"
                and len(pin) > 2 and pin.startswith("P")
                and pin[1] in "ABCDE" and pin[2:].isdigit()
            ]
            if not gpio_refs:
                continue
            first_pin = gpio_refs[0][1]
            shared = board.net("ABCDE".index(first_pin[1]), int(first_pin[2:]))
            for _cid, pin in gpio_refs:
                board.bind_schematic_pin("ABCDE".index(pin[1]), int(pin[2:]), shared)

        # 3) 生成器件并接网络
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
            self._spice_buttons.clear()
            self._spice_pots.clear()
            self._node_of_net = {}
            board.devices.pop("spice", None)
            return
        cc = CoupledCircuit(board, dt_ns=5_000)
        self.spice = cc
        self._spice_leds.clear()
        self._spice_buttons.clear()
        self._spice_pots.clear()
        board.devices["spice"] = cc
        # 只把实际参与模拟元件（R/C/LED/按键）的网络送入 MNA。
        # MCU 声明了 80 个 GPIO，但未接入模拟元件的空脚不能全部扩成 SPICE 节点，
        # 否则一个很小的 RC 电路也会被膨胀成百余维矩阵。
        spice_roots = set()
        for cid, comp in self.components.items():
            if comp["type"] in {"resistor", "capacitor", "led", "button"}:
                for pin in PIN_DEFS[comp["type"]]:
                    root = self.pin_net.get((cid, pin))
                    if root is not None:
                        spice_roots.add(root)

        # 网络名 -> 节点名；含 GND 元件的网络为参考地
        self._node_of_net = {}
        ground_roots = set()
        for cid, comp in self.components.items():
            if comp["type"] == "gnd":
                ground_roots.add(self.pin_net[(cid, "G")])
        for root in self.nets:
            self._node_of_net[root] = "GND" if root in ground_roots else f"n{root[:12]}"
        # 每个相连 GPIO 各自通过有限输出阻抗接入网络。
        # 输入引脚会呈高阻；多个输出误接时也不会把理想电源直接并联成奇异矩阵。
        for pin, root in self.mcu_pin_nets.items():
            if not (pin.startswith("P") and len(pin) > 2 and pin[1] in "ABCDE" and pin[2:].isdigit()):
                continue
            if root not in spice_roots:
                continue
            node = self._node_of_net.get(root)
            if node in (None, "GND"):
                continue
            cc.attach_pin(pin, node)
        powered_nodes = set()
        for cid, comp in self.components.items():
            if comp["type"] == "vcc":
                root = self.pin_net[(cid, "V")]
                if root not in spice_roots:
                    continue
                node = self._node_of_net.get(root)
                if node and node != "GND" and node not in powered_nodes:
                    src = cc.circuit.add_source(node, "GND")
                    src.volts = 3.3
                    powered_nodes.add(node)
        # R / C / LED / 按键和电位器
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
                    self._spice_buttons[cid] = cc.circuit.add_r(
                        na, nb, 10.0 if self.button_states.get(cid) else 10e6)
        # 电位器 wiper 经 10kΩ 等效输出阻抗接入模拟网络。
        # 这样输入 GPIO 能读取实际节点电压，输出 GPIO 也不会被理想电源强制钳位。
        for cid, comp in self.components.items():
            if comp["type"] != "pot":
                continue
            root = self.pin_net.get((cid, "W"))
            node = self._node_of_net.get(root)
            if root in spice_roots and node and node != "GND":
                drive_node = f"__pot_drive_{cid}"
                src = cc.circuit.add_source(drive_node, "GND")
                src.volts = self.pot_values.get(cid, 1.65)
                cc.circuit.add_r(drive_node, node, 10_000.0)
                self._spice_pots[cid] = src

        # 模拟网络可以只由 VCC/电路元件驱动、不含 MCU GPIO（例如纯 RC 电路）。
        # 只要已构建模拟元件就应步进，不能把 enabled 错误地绑定为“是否有 MCU 引脚源”。
        cc.enabled = bool(cc.circuit.comps)

    def _two_nodes(self, cid):
        comp = self.components[cid]
        pins = PIN_DEFS[comp["type"]]
        na = self._node_of_net.get(self.pin_net.get((cid, pins[0])))
        nb = self._node_of_net.get(self.pin_net.get((cid, pins[1])))
        return na, nb

    # ---------------- 运行期（引擎经 board.devices 每片调用）----------------
    def rebase_time(self):
        """固件重载/CPU 复位时同步 SPICE 时钟基准，不清除外部电路的电容状态。"""
        if self.spice is not None:
            self.spice.rebase_time(self.board.sysctrl.now_ns)

    def sample(self, now_ns: int):
        # 只有输入在整个 debounce_ms 窗口内保持稳定，才真正改变按键接点。
        for cid, (down, since_ns) in list(self.button_pending.items()):
            props = self.components.get(cid, {}).get("props", {})
            delay_ns = int(float(props.get("debounce_ms", 0.0)) * 1e6)
            if int(now_ns) - since_ns >= delay_ns:
                self.button_pending.pop(cid, None)
                self._apply_button_state(cid, down)
        for p in self.probes.values():
            p.sample(now_ns)

    def led_states(self) -> dict:
        """LED 运行态: on/brightness（SPICE 电流优先，否则数字电平+回路检查）。"""
        out = {}
        for cid, led in self.leds.items():
            on = led.on
            # 数字模式：负极必须接到 GND（有电流回路），否则视为断路不亮
            k_net = self.pin_net.get((cid, "K"))
            if k_net is None or k_net not in self._grounded:
                on = False
            bright = 1.0 if on else 0.0
            d = self._spice_leds.get(cid)
            if d is not None and self.spice is not None and self.spice.stepped:
                i = abs(d.i_last)
                on = i > 1e-3
                bright = max(0.0, min(1.0, i / 0.015))
            out[cid] = {"on": on, "brightness": round(bright, 3),
                        "color": led.color}
        return out

    def snapshot(self) -> dict:
        return {
            "mcu_powered": self.mcu_powered,
            "leds": self.led_states(),
            "buttons": {cid: b.pressed for cid, b in self.buttons.items()},
            "pots": {cid: p.volts for cid, p in self.pots.items()},
            "probes": {cid: [[round(t / 1e6, 4), round(v, 3)] for t, v in p.trace[-300:]]
                       for cid, p in self.probes.items()},
        }
