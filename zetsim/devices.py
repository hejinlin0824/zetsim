"""虚拟器件：LED / 按键 / 电位器 / 示波器 / SSD1306 OLED。"""
from __future__ import annotations


def _resolve_net(board, pin_or_net):
    """接受引脚名（'PA5'）或直接给 Net 对象（原理图模式）。"""
    if isinstance(pin_or_net, str):
        return board.net_by_name(pin_or_net)
    return pin_or_net


class Led:
    """LED（数字模式：高=亮；串阻时由 SPICE 电流决定亮度）。"""

    def __init__(self, board, name: str, pin, color: str = "red", vf: float = 2.0):
        self.name, self.color, self.vf = name, color, vf
        self.board = board
        self.net = _resolve_net(board, pin)
        self.on = False
        self.net.watchers.append(self._on_change)
        self._on_change(None, self.net.level)

    def _on_change(self, old, new):
        on = bool(new)
        if on != self.on:
            self.on = on
            self.board.publish(f"led.{self.name}", on)


class Button:
    """按键（注入电平到网络，默认松开=0）。"""

    def __init__(self, board, name: str, pin, active_high=True):
        self.name = name
        self.board = board
        self.net = _resolve_net(board, pin)
        self.net.set_device(0 if active_high else 1)   # 松开状态
        self.pressed = False

    def press(self):
        self.pressed = True
        self.board.publish(f"button.{self.name}", True)
        self.net.set_device(1)

    def release(self):
        self.pressed = False
        self.board.publish(f"button.{self.name}", False)
        self.net.set_device(0)

    def click(self):
        self.press()

    def schedule(self, times_ms: list[float]):
        """安排按键时刻（测试脚本用）。"""
        self._schedule = times_ms


class Potentiometer:
    """电位器：驱动网络的模拟电压（ADC 读它）。"""

    def __init__(self, board, name: str, pin, volts: float = 1.65):
        self.name = name
        self.board = board
        self.net = _resolve_net(board, pin)
        self.net.device_analog = volts
        self.volts = volts

    def set(self, volts: float):
        self.volts = max(0.0, min(3.3, volts))
        self.net.device_analog = self.volts


class Oscilloscope:
    """示波器：采样订阅引脚（数字边沿精确时间戳 + 周期采样模拟值）。"""

    def __init__(self, board, name: str, pins: list[str], period_ns: int = 50_000):
        self.name = name
        self.board = board
        self.period_ns = period_ns
        self.traces: dict[str, list[tuple[int, float]]] = {p: [] for p in pins}
        self._last_t = {p: 0 for p in pins}
        for p in pins:
            net = board.net_by_name(p)
            self.traces[p].append((board.sysctrl.now_ns, 0.0 if not net.level else 3.3))
            net.watchers.append(self._watcher(p))

    def _watcher(self, p):
        def w(old, new):
            t = self.board.sysctrl.now_ns
            self.traces[p].append((t, 3.3 if new == 1 else 0.0 if new == 0 else 1.65))
        return w

    def sample(self, now_ns):
        """周期采样（模拟量；数字已由 watcher 精确记录）。"""
        for p in list(self.traces):
            if now_ns - self._last_t[p] >= self.period_ns:
                self._last_t[p] = now_ns
                v = self.board.net_by_name(p).voltage()
                if v is not None:
                    self.traces[p].append((now_ns, v))

    def measure_frequency(self, pin: str, t0_ns=None, t1_ns=None) -> float | None:
        # 只用上升沿（上升->上升 = 完整周期）
        ev = [t for t, v in self.traces[pin]
              if v > 1.65 and (t0_ns is None or t >= t0_ns) and (t1_ns is None or t <= t1_ns)]
        if len(ev) < 3:
            return None
        periods = [p for p in (ev[i + 1] - ev[i] for i in range(len(ev) - 1)) if p > 0]
        if not periods:
            return None
        periods.sort()
        med = periods[len(periods) // 2]
        return 1e9 / med if med else None

    def measure_duty(self, pin: str, t0_ns=None, t1_ns=None) -> float | None:
        tr = self.traces[pin]
        seg = [(t, v) for t, v in tr if (t0_ns is None or t >= t0_ns) and (t1_ns is None or t <= t1_ns)]
        if len(seg) < 3:
            return None
        total = seg[-1][0] - seg[0][0]
        if total <= 0:
            return None
        high = 0.0
        for i in range(len(seg) - 1):
            dt = seg[i + 1][0] - seg[i][0]
            if seg[i][1] > 1.65:
                high += dt
        return high / total

    def avg_voltage(self, pin: str) -> float:
        tr = self.traces[pin]
        if len(tr) < 2:
            return 0.0
        total = tr[-1][0] - tr[0][0]
        s = 0.0
        for i in range(len(tr) - 1):
            s += (tr[i + 1][0] - tr[i][0]) * tr[i][1]
        return s / total if total else 0.0


class Ssd1306:
    """SSD1306 128x64 OLED（I2C 从机 0x3C）。"""

    WIDTH, HEIGHT = 128, 64

    def __init__(self, board, name: str, addr: int = 0x3C):
        self.name = name
        self.board = board
        self.addr = addr
        self.fb = bytearray(self.WIDTH * self.HEIGHT // 8)
        self.on = False
        self._mode = 0            # 0=命令 1=数据
        self._x = self._y = 0
        self._addr_mode = "page"
        self.dirty = True

    # ---- I2C 从机接口（由 I2C 控制器调用） ----
    def start(self, addr: int, read: bool) -> bool:
        return (addr << 1) == self.addr and not read

    def write(self, byte: int):
        if self._first:
            self._control = byte
            self._first = False
            return
        ctrl = self._control
        if ctrl & 0x40:                       # 数据
            self._data(byte)
        else:                                  # 命令（Co=0 单字节流）
            self._command(byte)

    _first = True
    _control = 0x00

    def repeat_start(self):
        self._first = True

    def stop(self):
        self._first = True
        if self.dirty:
            self.board.publish(f"oled.{self.name}.frame", None)
            self.dirty = False

    def _command(self, b: int):
        if b == 0xAF:
            self.on = True
        elif b == 0xAE:
            self.on = False
        elif b in (0x00,):
            self._x = 0
        elif 0x20 <= b <= 0x22:
            self._addr_mode = {0x20: "h", 0x21: "p", 0x22: "x"}.get(b, self._addr_mode)

    def _data(self, b: int):
        page = self._y
        if page < 8:
            base = page * self.WIDTH + self._x
            self.fb[base] = b
            self._x = (self._x + 1) % self.WIDTH
            if self._x == 0:
                self._y = (self._y + 1) % 8
        self.dirty = True

    def set_page_col(self, page: int, col: int):
        self._y = page & 7
        self._x = max(0, min(self.WIDTH - 1, col))

    def pixel(self, x: int, y: int) -> int:
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            return (self.fb[(y // 8) * self.WIDTH + x] >> (y % 8)) & 1
        return 0

    def count_on(self) -> int:
        return sum(bin(b).count("1") for b in self.fb)
