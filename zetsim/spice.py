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
        # Linear R/C/source networks reuse their MNA matrix factorization while
        # only source values and capacitor history terms change between steps.
        self._linear_lu_key: tuple | None = None
        self._linear_lu: tuple[list[list[float]], list[int]] | None = None
        self._linear_transition_key: tuple | None = None
        self._linear_transition: tuple[list[list[float]], list[list[float]]] | None = None

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

    def _linear_matrix_key(self, dt: float) -> tuple | None:
        """Return a matrix identity for linear R/C/source circuits, excluding RHS state."""
        parts = []
        for comp in self.comps:
            if isinstance(comp, Resistor):
                parts.append(("R", comp.n1.index, comp.n2.index, comp.r))
            elif isinstance(comp, Capacitor):
                parts.append(("C", comp.n1.index, comp.n2.index, comp.c))
            elif isinstance(comp, VoltageSource):
                parts.append(("V", comp.n1.index, comp.n2.index, comp.branch))
            else:
                # Diodes and any future nonlinear elements need the normal Newton path.
                return None
        nodes = tuple((name, node.index) for name, node in self.nodes.items())
        return dt, nodes, tuple(parts), len(self.sources)

    @staticmethod
    def _factor_matrix(matrix: list[list[float]]) -> tuple[list[list[float]], list[int]] | None:
        """LU factorization with partial pivoting; None denotes a singular matrix."""
        lu = [row[:] for row in matrix]
        size = len(lu)
        pivots: list[int] = []
        for col in range(size):
            pivot = max(range(col, size), key=lambda row: abs(lu[row][col]))
            if abs(lu[pivot][col]) < 1e-15:
                return None
            pivots.append(pivot)
            if pivot != col:
                lu[col], lu[pivot] = lu[pivot], lu[col]
            diagonal = lu[col][col]
            for row in range(col + 1, size):
                lu[row][col] /= diagonal
                multiplier = lu[row][col]
                for idx in range(col + 1, size):
                    lu[row][idx] -= multiplier * lu[col][idx]
        return lu, pivots

    @staticmethod
    def _solve_factored(factorization: tuple[list[list[float]], list[int]],
                        rhs: list[float]) -> list[float]:
        """Solve LU*x=rhs, applying the same recorded row swaps as factorization."""
        lu, pivots = factorization
        values = rhs[:]
        size = len(values)
        for col, pivot in enumerate(pivots):
            if pivot != col:
                values[col], values[pivot] = values[pivot], values[col]
            pivot_value = values[col]
            for row in range(col + 1, size):
                values[row] -= lu[row][col] * pivot_value
        for row in range(size - 1, -1, -1):
            residual = values[row]
            for col in range(row + 1, size):
                residual -= lu[row][col] * values[col]
            values[row] = residual / lu[row][row]
        return values

    @staticmethod
    def _matrix_multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
        rows, inner, cols = len(a), len(b), len(b[0]) if b else 0
        out = [[0.0] * cols for _ in range(rows)]
        for row in range(rows):
            for k in range(inner):
                value = a[row][k]
                if value:
                    for col in range(cols):
                        out[row][col] += value * b[k][col]
        return out

    @staticmethod
    def _matrix_vector_multiply(matrix: list[list[float]], vector: list[float]) -> list[float]:
        return [sum(value * vector[col] for col, value in enumerate(row))
                for row in matrix]

    @classmethod
    def _matrix_power_apply(cls, matrix: list[list[float]], exponent: int,
                            vector: list[float]) -> list[float]:
        """Apply matrix**exponent to vector via repeated squaring."""
        result = vector[:]
        power = matrix
        remaining = int(exponent)
        while remaining:
            if remaining & 1:
                result = cls._matrix_vector_multiply(power, result)
            remaining >>= 1
            if remaining:
                power = cls._matrix_multiply(power, power)
        return result

    @staticmethod
    def _cap_voltage(capacitor: Capacitor, solution: list[float]) -> float:
        va = solution[capacitor.n1.index] if capacitor.n1.index else 0.0
        vb = solution[capacitor.n2.index] if capacitor.n2.index else 0.0
        return va - vb

    def _ensure_linear_factorization(self, dt: float) -> tuple | None:
        """Build/reuse LU for a linear network; return its matrix key."""
        matrix_key = self._linear_matrix_key(dt)
        if matrix_key is None:
            return None
        n = len(self.nodes)
        size = n + len(self.sources)
        for i, source in enumerate(self.sources):
            source.branch = n + i
        # Recompute the key after branch numbers have been assigned.
        matrix_key = self._linear_matrix_key(dt)
        if matrix_key is None:
            return None
        if matrix_key != self._linear_lu_key:
            g = [[0.0] * size for _ in range(size)]
            b = [0.0] * size
            for comp in self.comps:
                comp.stamp(g, b, dt, self.sources)
            reduced = [row[1:] for row in g[1:]]
            self._linear_lu = self._factor_matrix(reduced)
            self._linear_lu_key = matrix_key
            self._linear_transition_key = None
            self._linear_transition = None
        return matrix_key if self._linear_lu is not None else None

    def _get_linear_transition(self, dt: float) -> tuple[list[list[float]], list[list[float]]] | None:
        """Map previous capacitor voltages and source levels to next capacitor voltages."""
        matrix_key = self._ensure_linear_factorization(dt)
        if matrix_key is None or self._linear_lu is None:
            return None
        if matrix_key == self._linear_transition_key and self._linear_transition is not None:
            return self._linear_transition

        capacitors = [comp for comp in self.comps if isinstance(comp, Capacitor)]
        q = len(capacitors)
        if not q:
            return None
        size = len(self.nodes) + len(self.sources)
        factorization = self._linear_lu
        response_to_caps = [[0.0] * q for _ in range(q)]
        response_to_sources = [[0.0] * len(self.sources) for _ in range(q)]

        # Each capacitor's history voltage contributes a fixed column to the RHS.
        for col, capacitor in enumerate(capacitors):
            rhs = [0.0] * size
            equivalent_g = capacitor.c / dt
            if capacitor.n1.index:
                rhs[capacitor.n1.index] += equivalent_g
            if capacitor.n2.index:
                rhs[capacitor.n2.index] -= equivalent_g
            solved = [0.0] + self._solve_factored(factorization, rhs[1:])
            for row, measured in enumerate(capacitors):
                response_to_caps[row][col] = self._cap_voltage(measured, solved)

        # Each independent source contributes one column to the RHS.
        for col, source in enumerate(self.sources):
            rhs = [0.0] * size
            rhs[source.branch] = 1.0
            solved = [0.0] + self._solve_factored(factorization, rhs[1:])
            for row, measured in enumerate(capacitors):
                response_to_sources[row][col] = self._cap_voltage(measured, solved)

        self._linear_transition = (response_to_caps, response_to_sources)
        self._linear_transition_key = matrix_key
        return self._linear_transition

    def step_repeated(self, dt: float, repeats: int) -> bool:
        """Advance a linear RC network by N identical fixed steps without a Python step loop.

        This is algebraically equivalent to repeatedly calling step(dt): the same
        backward-Euler transition is exponentiated while input sources stay constant.
        Nonlinear or singular networks return False so the caller can use the normal solver.
        """
        repeats = int(repeats)
        if repeats < 1:
            return True
        transition = self._get_linear_transition(dt)
        if transition is None:
            return False
        capacitors = [comp for comp in self.comps if isinstance(comp, Capacitor)]
        a_matrix, b_matrix = transition
        q = len(capacitors)

        # Affine state recurrence v[n+1] = A*v[n] + B*source_volts.
        drive = [
            sum(b_matrix[row][col] * source.volts
                for col, source in enumerate(self.sources))
            for row in range(q)
        ]
        augmented = [
            a_matrix[row][:] + [drive[row]]
            for row in range(q)
        ]
        augmented.append([0.0] * q + [1.0])
        state = [capacitor.vprev for capacitor in capacitors] + [1.0]
        before_last = self._matrix_power_apply(augmented, repeats - 1, state)

        # Solve the final step once so Circuit._last, diode-free component state,
        # and capacitor commits have the same meaning as the ordinary repeated path.
        size = len(self.nodes) + len(self.sources)
        rhs = [0.0] * size
        for capacitor, old_voltage in zip(capacitors, before_last[:q]):
            equivalent_g = capacitor.c / dt
            if capacitor.n1.index:
                rhs[capacitor.n1.index] += equivalent_g * old_voltage
            if capacitor.n2.index:
                rhs[capacitor.n2.index] -= equivalent_g * old_voltage
        for source in self.sources:
            rhs[source.branch] = source.volts
        solution = [0.0] + self._solve_factored(self._linear_lu, rhs[1:])
        self._last = solution
        for comp in self.comps:
            if hasattr(comp, "commit"):
                comp.commit(solution)
        return True

    def _build_and_solve(self, dt):
        n = len(self.nodes)                 # 节点索引 0..n-1（0=GND）
        m = len(self.sources)
        size = n + m
        for i, source in enumerate(self.sources):
            source.branch = n + i

        # In a linear R/C network, topology and component values determine the
        # MNA coefficient matrix; source voltages and capacitor history only
        # change the RHS. Factor once, then solve each transient step in O(N^2).
        matrix_key = self._linear_matrix_key(dt)
        if matrix_key is not None:
            if matrix_key != self._linear_lu_key:
                g = [[0.0] * size for _ in range(size)]
                b = [0.0] * size
                for comp in self.comps:
                    comp.stamp(g, b, dt, self.sources)
                # Ground is fixed at 0V, so remove its all-zero row/column before LU.
                reduced = [row[1:] for row in g[1:]]
                self._linear_lu = self._factor_matrix(reduced)
                self._linear_lu_key = matrix_key
            if self._linear_lu is not None:
                b = [0.0] * size
                for comp in self.comps:
                    if isinstance(comp, Capacitor):
                        equivalent_g = comp.c / dt
                        a, c = comp.n1.index, comp.n2.index
                        if a:
                            b[a] += equivalent_g * comp.vprev
                        if c:
                            b[c] -= equivalent_g * comp.vprev
                    elif isinstance(comp, VoltageSource):
                        b[comp.branch] = comp.volts
                x = [0.0] + self._solve_factored(self._linear_lu, b[1:])
                for comp in self.comps:
                    if hasattr(comp, "commit"):
                        comp.commit(x)
                return x

        # Nonlinear circuits and singular linear networks retain the established
        # Newton iteration with the original direct solver as a correctness fallback.
        for _ in range(30):                       # 二极管 Newton 外层迭代
            g = [[0.0] * size for _ in range(size)]
            b = [0.0] * size
            for comp in self.comps:
                comp.stamp(g, b, dt, self.sources)
            # Newton changes the diode conductance each iteration, so its matrix
            # cannot share a cached factorization. Still use LU rather than full
            # Gauss-Jordan elimination to reduce work for each nonlinear substep.
            factorization = self._factor_matrix([row[1:] for row in g[1:]])
            if factorization is None:
                x = _solve_linear(g, b)
            else:
                x = [0.0] + self._solve_factored(factorization, b[1:])
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
        # For memoryless networks, only the DC operating point is needed when
        # a source or resistor value changes; there is no reason to solve every 5 us.
        self._last_static_signature: tuple | None = None
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

            if not getattr(self.board, "mcu_power", True):
                resistor.r = 1e12
                continue

            key = (port_idx, pin_idx)
            if mode == 0:
                if cnf == 0b10:  # 输入上拉/下拉：典型值近似 40kΩ，ODR 选择方向
                    odr_bit = (self.board.gpios[port_idx]._odr() >> pin_idx) & 1
                    source.volts = 3.3 if odr_bit else 0.0
                    resistor.r = 40_000.0
                else:
                    resistor.r = 1e12
                continue

            # 同一电气网可能包含多个 MCU 引脚；每个 SPICE 驱动读取自己的输出级状态。
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
        self._sync_pin_drivers()
        # A reset may keep the same pin voltages while resetting other circuit state.
        self._last_static_signature = None

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

    def _static_input_signature(self) -> tuple:
        """Values that determine a memoryless DC operating point.

        Diode internal Newton state is intentionally excluded: once the operating
        point has converged, it does not need to be solved again until an external
        source or resistance changes.
        """
        source_values = tuple(source.volts for source in self.circuit.sources)
        resistor_values = tuple(
            comp.r for comp in self.circuit.comps if isinstance(comp, Resistor)
        )
        return source_values, resistor_values

    def step(self, now_ns: int):
        if not self.enabled:
            return
        now = int(now_ns)
        if now < self._last_ns:
            # 防御调用方复位时间源却忘了同步本耦合器的情况。
            self.rebase_time(now)
            return
        # 本次积分必须使用上一片末缓存的 GPIO 状态。对于含电容的瞬态网络，
        # CPU/定时器在当前片末产生的边沿只能影响下一片，不能追溯应用到已逝去的区间。
        elapsed = max(0, now - self._last_ns)
        self._last_ns = now

        # Memoryless-network caching is supported by the real Circuit implementation.
        # Older test doubles may intentionally expose only step()/voltage(); preserve
        # their fixed-step contract instead of requiring an undocumented .comps attribute.
        components = getattr(self.circuit, "comps", None)
        if components is not None and not any(isinstance(comp, Capacitor) for comp in components):
            self._sync_pin_drivers()
            signature = self._static_input_signature()
            if not self.stepped or signature != self._last_static_signature:
                self.circuit.step(self.dt_ns / 1e9)
                self.stepped = True
                self._last_static_signature = signature
            self._sample_pin_voltages()
            for name, node in self.probes.items():
                self.history[name].append((now, self.circuit.voltage(node)))
            return

        self._remainder_ns += elapsed
        n_sub = self._remainder_ns // self.dt_ns
        if n_sub <= 0:
            self._sync_pin_drivers()
            self._sample_pin_voltages()
            return
        # 不超过时间片实际经过的固定步数；不足 dt 的尾数保留到下一次调用，
        # 避免短片/高频事件导致模拟时间被人为加速。
        n_sub = min(int(n_sub), self.max_substeps)
        batched = False
        if n_sub > 1:
            advance_many = getattr(self.circuit, "step_repeated", None)
            if advance_many is not None:
                batched = bool(advance_many(self.dt_ns / 1e9, n_sub))
        if not batched:
            for _ in range(n_sub):
                self.circuit.step(self.dt_ns / 1e9)
        self._remainder_ns -= n_sub * self.dt_ns
        self.stepped = True
        # 解完上一状态之后，采集当前 GPIO 驱动，供下一个仿真时间区间使用。
        self._sync_pin_drivers()
        self._sample_pin_voltages()
        for name, node in self.probes.items():
            self.history[name].append((now_ns, self.circuit.voltage(node)))
