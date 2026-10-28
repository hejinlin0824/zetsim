"""mini-SPICE — 内置小型模拟电路求解器（M7 混合仿真）。

为什么内置而不接 ngspice：个人学习场景要零外部 DLL 依赖、完全自控。
实现：节点分析法(MNA) + 后向欧拉（电容伴随模型）+ 二极管 Newton 迭代。
支持 R / C / 分段常数电压源（MCU 引脚驱动）/ LED 二极管。
足以精确求解 RC 滤波、LED 限流等教学电路（误差 <2%）。
"""
from __future__ import annotations
import math


class Node:
    __slots__ = ("name", "index")

    def __init__(self, name: str, index: int):
        self.name, self.index = name, index      # 0 = GND


class Resistor:
    def __init__(self, n1: Node, n2: Node, ohms: float):
        self.n1, self.n2, self.r = n1, n2, ohms

    def stamp(self, g, b, dt, sources):
        y = 1.0 / self.r
        a, c = self.n1.index, self.n2.index
        if a: g[a][a] += y
        if c: g[c][c] += y
        if a and c:
            g[a][c] -= y
            g[c][a] -= y


class Capacitor:
    """后向欧拉: geq = C/dt, 历史项 = geq * v_prev"""

    def __init__(self, n1: Node, n2: Node, farads: float):
        self.n1, self.n2, self.c = n1, n2, farads
        self.vprev = 0.0

    def stamp(self, g, b, dt, sources):
        geq = self.c / dt
        a, c = self.n1.index, self.n2.index
        if a:
            g[a][a] += geq
            b[a] += geq * self.vprev
        if c:
            g[c][c] += geq
            b[c] -= geq * self.vprev
        if a and c:
            g[a][c] -= geq
            g[c][a] -= geq

    def commit(self, x):
        v1 = x[self.n1.index] if self.n1.index else 0.0
        v2 = x[self.n2.index] if self.n2.index else 0.0
        self.vprev = v1 - v2


class Diode:
    """指数特性: i = Is*(e^(vd/nVt)-1)，Newton 线性化"""

    def __init__(self, na: Node, nk: Node, is_: float = 1e-15, n_vt: float = 0.05):
        self.na, self.nk, self.is_, self.nvt = na, nk, is_, n_vt
        self.vd_prev = 0.0
        self.i_last = 0.0

    def _lin(self):
        e = min(self.vd_prev / self.nvt, 60.0)
        i = self.is_ * (math.exp(e) - 1)
        gd = self.is_ * math.exp(e) / self.nvt
        return gd, i - gd * self.vd_prev

    def stamp(self, g, b, dt, sources):
        gd, ieq = self._lin()
        a, c = self.na.index, self.nk.index
        if a:
            g[a][a] += gd
            b[a] -= ieq
        if c:
            g[c][c] += gd
            b[c] += ieq
        if a and c:
            g[a][c] -= gd
            g[c][a] -= gd

    def vd_of(self, x):
        va = x[self.na.index] if self.na.index else 0.0
        vk = x[self.nk.index] if self.nk.index else 0.0
        return va - vk

    def commit(self, x):
        self.vd_prev = self.vd_of(x)
        e = min(self.vd_prev / self.nvt, 60.0)
        self.i_last = self.is_ * (math.exp(e) - 1)


class VoltageSource:
    """分段常数源（MCU 引脚 0/3.3V），MNA 附加支路（branch 号由 Circuit 分配）"""

    def __init__(self, n1: Node, n2: Node):
        self.n1, self.n2 = n1, n2
        self.volts = 0.0
        self.branch = 0

    def stamp(self, g, b, dt, sources):
        k = self.branch
        a, c = self.n1.index, self.n2.index
        if a:
            g[a][k] += 1
            g[k][a] += 1
        if c:
            g[c][k] -= 1
            g[k][c] -= 1
        b[k] = self.volts


class Circuit:
    def __init__(self):
        self.nodes: dict[str, Node] = {"GND": Node("GND", 0)}
        self.comps: list = []
        self.sources: list[VoltageSource] = []
        self._n_nodes = 1

    def node(self, name: str) -> Node:
        if name not in self.nodes:
            self.nodes[name] = Node(name, len(self.nodes))
        return self.nodes[name]

    def add_r(self, a, b_, ohms) -> Resistor:
        resistor = Resistor(self.node(a), self.node(b_), ohms)
        self.comps.append(resistor)
        return resistor

    def add_c(self, a, b_, farads):
        c = Capacitor(self.node(a), self.node(b_), farads)
        self.comps.append(c)
        return c

    def add_led(self, a, b_, is_=1e-15, n_vt=0.05):
        d = Diode(self.node(a), self.node(b_), is_, n_vt)
        self.comps.append(d)
        return d

    def add_source(self, a, b_) -> VoltageSource:
        v = VoltageSource(self.node(a), self.node(b_))
        self.comps.append(v)
        self.sources.append(v)
        return v

    def _build_and_solve(self, dt):
        n = len(self.nodes)                 # 节点索引 0..n-1（0=GND）
        m = len(self.sources)
        size = n + m
        for i, s in enumerate(self.sources):
            s.branch = n + i
        for _ in range(30):                       # 二极管 Newton 外层迭代
            g = [[0.0] * size for _ in range(size)]
            b = [0.0] * size
            for comp in self.comps:
                comp.stamp(g, b, dt, self.sources)
            x = _solve_linear(g, b)
            dv = 0.0
            for comp in self.comps:
                if isinstance(comp, Diode):
                    dv = max(dv, abs(comp.vd_of(x) - comp.vd_prev))
                    comp.vd_prev = comp.vd_of(x)
            if dv < 1e-3:
                break
        for comp in self.comps:                   # 状态提交
            if hasattr(comp, "commit"):
                comp.commit(x)
        return x

    def step(self, dt: float) -> list[float]:
        self._last = self._build_and_solve(dt)
        return self._last

    def voltage(self, name: str) -> float:
        return self._last[self.nodes[name].index] if hasattr(self, "_last") else 0.0


def _solve_linear(g, b):
    """高斯-约当消元（电路规模小）"""
    n = len(b)
    a = [row[:] + [b[i]] for i, row in enumerate(g)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-15:
            continue
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col] / pv
                for c2 in range(col, n + 1):
                    a[r][c2] -= f * a[col][c2]
    return [a[i][n] / a[i][i] if abs(a[i][i]) > 1e-15 else 0.0 for i in range(n)]


# ---------------- 与引擎的耦合：MCU 引脚 -> 电源 ----------------
class CoupledCircuit:
    """MCU 数字引脚经 VoltageSource 驱动模拟电路，每个仿真片步进求解。"""

    def __init__(self, board: "Board", dt_ns: int = 5_000):    # type: ignore
        from zetsim.spice import Circuit
        self.board = board
        self.circuit = Circuit()
        self.dt_ns = dt_ns
        self.pin_sources: dict[str, VoltageSource] = {}
        self.pin_resistors: dict[str, Resistor] = {}  # GPIO 输出级的有限驱动阻抗
        self.stepped = False                    # 引擎步进过至少一次（否则电流无效）
        self.probes: dict[str, str] = {}        # 探针名 -> 节点名
        self.history: dict[str, list[tuple[int, float]]] = {}
        self.enabled = False
        self._last_ns = board.sysctrl.now_ns
        self._remainder_ns = 0
        self._prev_volts: dict[str, float] = {}
        self.max_substeps = 2000

    def attach_pin(self, pin: str, node_a: str):
        """GPIO 经有限输出阻抗接入模拟网；输入模式或开漏释放时应呈高阻，而不是强拉 0V。"""
        if not (pin.startswith("P") and len(pin) > 2 and pin[1] in "ABCDE"
                and pin[2:].isdigit()):
            raise ValueError(f"不是有效的 GPIO 引脚名：{pin}")
        drive_node = f"__gpio_drive_{pin}"
        src = self.circuit.add_source(drive_node, "GND")
        resistor = self.circuit.add_r(drive_node, node_a, 1e12)
        self.pin_sources[pin] = src
        self.pin_resistors[pin] = resistor
        self._prev_volts[pin] = 0.0
        self.enabled = True
        self._sync_pin_drivers()
        return src

    def _sync_pin_drivers(self):
        """按当前 GPIO 配置更新源值与输出阻抗；模拟输入不能被 MCU 的虚拟 0V 源短路。"""
        for pin, source in self.pin_sources.items():
            port_idx = "ABCDE".index(pin[1])
            pin_idx = int(pin[2:])
            net = self.board.resolved_net(port_idx, pin_idx)
            mode, cnf = self.board.gpios[port_idx].pin_cfg(pin_idx)
            resistor = self.pin_resistors[pin]

            if not getattr(self.board, "mcu_power", True) or mode == 0:
                resistor.r = 1e12
                continue

            # 同一电气网可能包含多个 MCU 引脚；每个 SPICE 驱动必须读取自己的输出级状态。
            key = (port_idx, pin_idx)
            if cnf in (0b10, 0b11):
                level = net.af_outputs.get(key, net.af_level)
            else:
                level = net.mcu_outputs.get(key, net.mcu_level)
            if level is None:
                # 开漏输出写 1 是释放引脚，必须由外部上拉决定电平。
                resistor.r = 1e12
            else:
                source.volts = 3.3 if level else 0.0
                resistor.r = 25.0

    def rebase_time(self, now_ns: int | None = None):
        """CPU/仿真复位后重置时间基准，但保留电容电压等外部电路状态。"""
        now = int(self.board.sysctrl.now_ns if now_ns is None else now_ns)
        self._last_ns = now
        self._remainder_ns = 0
        for pin, src in self.pin_sources.items():
            if pin.startswith("P") and len(pin) > 2 and pin[1] in "ABCDE" and pin[2:].isdigit():
                net = self.board.resolved_net("ABCDE".index(pin[1]), int(pin[2:]))
                voltage = net.voltage()
            else:
                voltage = src.volts
            value = voltage if voltage is not None else 0.0
            src.volts = value
            self._prev_volts[pin] = value

    def _sample_pin_voltages(self):
        """采样本片末的 MCU 网络电平，短于 SPICE 步长的时间片也不能跳过采样。"""
        for pin in self.pin_sources:
            if not (pin.startswith("P") and len(pin) > 2 and pin[1] in "ABCDE"
                    and pin[2:].isdigit()):
                continue
            net = self.board.resolved_net("ABCDE".index(pin[1]), int(pin[2:]))
            voltage = net.voltage()
            self._prev_volts[pin] = voltage if voltage is not None else 0.0

    def probe(self, name: str, node: str):
        self.probes[name] = node
        self.history.setdefault(name, [])

    def step(self, now_ns: int):
        if not self.enabled:
            return
        if int(now_ns) < self._last_ns:
            # 防御调用方复位时间源却忘了同步本耦合器的情况。
            self.rebase_time(now_ns)
            return
        # 在求解前读取本片最新 GPIO 配置和驱动状态；输入/开漏释放均为高阻。
        self._sync_pin_drivers()
        elapsed = max(0, int(now_ns) - self._last_ns)
        self._last_ns = int(now_ns)
        self._remainder_ns += elapsed
        n_sub = self._remainder_ns // self.dt_ns
        if n_sub <= 0:
            self._sample_pin_voltages()
            return
        # 不超过时间片实际经过的固定步数；不足 dt 的尾数保留到下一次调用，
        # 避免短片/高频事件导致模拟时间被人为加速。
        n_sub = min(int(n_sub), self.max_substeps)
        for _ in range(n_sub):
            self.circuit.step(self.dt_ns / 1e9)
        self._remainder_ns -= n_sub * self.dt_ns
        self.stepped = True
        self._sample_pin_voltages()
        for name, node in self.probes.items():
            self.history[name].append((now_ns, self.circuit.voltage(node)))
