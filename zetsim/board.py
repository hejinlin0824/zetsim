"""Board — STM32F103ZET6 整机：MCU 外设集合 + 引脚网络 + 器件容器。"""
from __future__ import annotations
from .bus import SystemBus, StubRegion
from .core import CortexM3Core
from .timebase import ConstantTimeModel, ClockTree
from .events import EventBus
from .periph import Peripheral
from .periph.sysctrl import SysCtrl
from .periph.rcc import Rcc
from .periph.gpio import Gpio
from .periph.afio_exti import Afio, Exti
from .periph.usart import Usart
from .periph.tim import Timer
from .periph.adc import Adc
from .periph.dma import Dma
from .periph.spi import Spi
from .periph.i2c import I2c
from .periph.dac import Dac

PORTS = "ABCDE"


class Net:
    """一根导线：MCU 输出 / AF 输出 / 器件驱动 三方 + 模拟电压。"""

    def __init__(self, name: str):
        self.name = name
        self.mcu_level = None        # 兼容旧接口的单一 MCU 驱动
        self.af_level = None         # 兼容旧接口的单一 AF 驱动
        self.mcu_outputs: dict[tuple[int, int], int] = {}  # 同网多 MCU 引脚各自的驱动
        self.af_outputs: dict[tuple[int, int], int] = {}   # 同网多 AF 引脚各自的驱动
        self.device_level = None     # 器件强驱动（按键）
        self.device_analog = None    # 模拟驱动（电位器）
        self.mcu_analog = None       # MCU 模拟输出（DAC）
        self.mcu_pulls: dict[tuple[int, int], int] = {}  # 输入上下拉：弱驱动，按物理引脚分别记录
        self.level = None            # 解析结果缓存
        self.watchers: list = []
        self.power_gate = None       # Board 引用：mcu_power=False 时 MCU 侧输出高阻

    def _resolve(self):
        gate = self.power_gate
        mcu_powered = gate is None or getattr(gate, "mcu_power", True)
        if mcu_powered:
            mcu_drivers = set(self.mcu_outputs.values())
            af_drivers = set(self.af_outputs.values())
            if self.mcu_level is not None:
                mcu_drivers.add(self.mcu_level)
            if self.af_level is not None:
                af_drivers.add(self.af_level)
            strong_drivers = mcu_drivers | af_drivers
            if len(strong_drivers) > 1:
                # 直接相连的强驱动相互冲突：电平在数字抽象里未定义，不能伪造确定的 0/1。
                return None
            if strong_drivers:
                return next(iter(strong_drivers))
            if self.device_level is not None:
                return self.device_level
            pulls = set(self.mcu_pulls.values())
            if len(pulls) == 1:
                return pulls.pop()
            # 没有拉电阻或相反方向弱拉冲突时，视为浮空/不确定。
            return None
        # 掉电后，MCU 输出和内部上下拉都失效；外部器件仍然可以驱动线路。
        return self.device_level

    def voltage(self) -> float | None:
        if self.device_analog is not None:
            return self.device_analog
        if self.mcu_analog is not None:
            return self.mcu_analog
        if self.level == 1:
            return 3.3
        if self.level == 0:
            return 0.0
        return None

    def set_mcu(self, lv, key: tuple[int, int] | None = None):
        if key is None:
            changed = self.mcu_level != lv
            self.mcu_level = lv
        else:
            old = self.mcu_outputs.get(key)
            changed = old != lv
            if lv is None:
                self.mcu_outputs.pop(key, None)
            else:
                self.mcu_outputs[key] = int(lv)
        if changed:
            self._commit()

    def set_af(self, lv, key: tuple[int, int] | None = None):
        if key is None:
            changed = self.af_level != lv
            self.af_level = lv
        else:
            old = self.af_outputs.get(key)
            changed = old != lv
            if lv is None:
                self.af_outputs.pop(key, None)
            else:
                self.af_outputs[key] = int(lv)
        if changed:
            self._commit()

    def set_device(self, lv):
        if self.device_level != lv:
            self.device_level = lv
            self._commit()

    def set_mcu_pull(self, key: tuple[int, int], level: int | None):
        """设置一个 MCU 引脚的内部弱上拉/下拉；None 表示断开该弱驱动。"""
        if level not in (None, 0, 1):
            raise ValueError("内部上下拉电平必须为 0、1 或 None")
        if level is None:
            self.mcu_pulls.pop(key, None)
        else:
            self.mcu_pulls[key] = int(level)
        self._commit()

    def reset_bindings(self):
        """原理图重建：清掉所有驱动与器件 watcher（保留板级 EXTI watcher）。"""
        self.mcu_level = None
        self.af_level = None
        self.mcu_outputs.clear()
        self.af_outputs.clear()
        self.device_level = None
        self.device_analog = None
        self.mcu_analog = None
        self.mcu_pulls.clear()
        self.watchers = [w for w in self.watchers if getattr(w, "__self__", None) is None
                         and getattr(w, "_board_watch", False)]
        self._commit()

    def _commit(self):
        new = self._resolve()
        if new != self.level:
            old = self.level
            self.level = new
            for w in self.watchers:
                w(old, new)


class Board:
    """F103ZET6。events + 可选器件接线。"""

    def __init__(self, cpi: float = 2.0):
        self.mcu_power = True       # 电源门控：原理图 VDD/VSS 都接好才为 True
        self.events = EventBus()
        self.time_model = ConstantTimeModel(cpi)
        self.clock = ClockTree()
        self.bus = SystemBus()
        # 内存与外设
        self.mcu = self
        self.core = CortexM3Core(self.bus, self.time_model)
        self.rcc = Rcc()
        self.clock.rcc = self.rcc
        self.sysctrl = SysCtrl()
        self.sysctrl.core = self.core
        self.core.nvic = self.sysctrl
        self.gpios = [Gpio(i) for i in range(5)]
        self.afio = Afio()
        self.exti = Exti()
        self.exti.afio = self.afio
        self.usarts = {i: Usart(i) for i in (1, 2, 3, 4, 5)}
        self.timers = {i: Timer(i) for i in (1, 2, 3, 4, 5, 6, 7, 8)}
        self.adcs = {i: Adc(i) for i in (1, 2, 3)}
        self.dma = Dma(1)
        self.dma2 = Dma(2)
        self.spis = {i: Spi(i) for i in (1, 2, 3)}
        self.i2cs = {i: I2c(i) for i in (1, 2)}
        self.dac = Dac()

        # 总线装配
        self.bus.add(self.core.FLASH_BASE, self.core.FLASH_SIZE, "rom")
        self.bus.add(self.core.SRAM_BASE, self.core.SRAM_SIZE, "ram")
        self._add_periph(self.rcc)
        self._add_periph(self.sysctrl)
        self._add_periph(self.afio)
        self._add_periph(self.exti)
        for g in self.gpios:
            self._add_periph(g)
        for u in self.usarts.values():
            self._add_periph(u)
        for t in self.timers.values():
            self._add_periph(t)
        for adc in self.adcs.values():
            self._add_periph(adc)
        self._add_periph(self.dma)
        self._add_periph(self.dma2)
        for s in self.spis.values():
            self._add_periph(s)
        for i2c in self.i2cs.values():
            self._add_periph(i2c)
        self._add_periph(self.dac)
        self._add_stubs()
        for p in self.all_periphs():
            p.board = self
            p.clock = self.clock
        self.rcc.on_enable_change = self._resync_gates
        # DMA 请求源绑定：ADC1 EOC -> DMA1 通道1
        self.adcs[1]._dma = self.dma
        self.adcs[1].dma_ch = 0
        self.dma.bus = self.bus

        # 引脚网络
        self.nets: dict[tuple[int, int], Net] = {}
        self.schematic_nets: dict[str, Net] = {}
        # 原理图中的多个 MCU 引脚可以共享同一个电气网络；物理引脚 Net 本身仍单独保存，
        # 通过 resolved_net() 在运行期解析到共享网络，避免只在网表层 union、CPU 侧却脱节。
        self.schematic_pin_nets: dict[tuple[int, int], Net] = {}
        # 器件
        self.devices: dict[str, object] = {}

    # ---------------- 装配 ----------------
    def _add_periph(self, p: Peripheral):
        self.bus.add(p.base, p.size, "periph", p)

    def _add_stubs(self):
        for name, base, size in (("USB", 0x40005C00, 0x400), ("bxCAN1", 0x40006400, 0x400),
                                 ("bxCAN2", 0x40006800, 0x400), ("BKP", 0x40006C00, 0x400),
                                 ("PWR", 0x40007000, 0x400), ("SDIO", 0x40018000, 0x400),
                                 ("IWDG", 0x40003000, 0x400), ("WWDG", 0x40002C00, 0x400),
                                 ("RTC", 0x40002800, 0x400)):
            self.bus.add(base, size, "stub", StubRegion(name))

    def all_periphs(self):
        yield self.sysctrl
        yield self.rcc
        yield self.afio
        yield self.exti
        for g in self.gpios:
            yield g
        for u in self.usarts.values():
            yield u
        for t in self.timers.values():
            yield t
        for a in self.adcs.values():
            yield a
        for s in self.spis.values():
            yield s
        for i in self.i2cs.values():
            yield i
        yield self.dma
        yield self.dma2
        yield self.dac

    def attach(self, p: Peripheral):
        """后期挂载外设（TIM/ADC/...）。"""
        self._add_periph(p)
        p.board = self
        p.clock = self.clock

    def _resync_gates(self):
        for p in self.all_periphs():
            p.sync_clock_gate()

    # ---------------- 引脚 ----------------
    def net(self, port_idx: int, pin: int) -> Net:
        key = (port_idx, pin)
        if key not in self.nets:
            n = Net(f"P{PORTS[port_idx]}{pin}")
            n.power_gate = self
            w = lambda old, new, k=key: self._net_changed(k, old, new)
            w._board_watch = True                 # reset_bindings 保留的板级 watcher
            n.watchers.append(w)
            self.nets[key] = n
        return self.nets[key]

    def net_by_name(self, name: str) -> Net:
        port_idx = PORTS.index(name[1])
        return self.net(port_idx, int(name[2:]))

    def schematic_net(self, net_id: str) -> Net:
        """原理图中间结点的合成网络（非 MCU 引脚）。"""
        if net_id not in self.schematic_nets:
            n = Net(net_id)
            n.power_gate = self
            n.watchers.append(lambda old, new, k=net_id:
                              self.events.publish(self.sysctrl.now_ns, f"net.{k}", new))
            self.schematic_nets[net_id] = n
        return self.schematic_nets[net_id]

    def resolved_net(self, port_idx: int, pin: int) -> Net:
        """返回原理图解析后的电气网络；未绑定时退回物理引脚自己的 Net。"""
        key = (port_idx, pin)
        return self.schematic_pin_nets.get(key) or self.net(port_idx, pin)

    def bind_schematic_pin(self, port_idx: int, pin: int, target: Net):
        """把 MCU 引脚接入原理图的共享网络，并为该引脚保留 GPIO/EXTI 观察器。"""
        key = (port_idx, pin)
        physical = self.net(port_idx, pin)
        self.schematic_pin_nets[key] = target
        if target is physical:
            return
        if any(getattr(w, "_schematic_alias_key", None) == key for w in target.watchers):
            return
        watcher = lambda old, new, k=key: self._net_changed(k, old, new)
        watcher._board_watch = True
        watcher._schematic_alias = True
        watcher._schematic_alias_key = key
        target.watchers.append(watcher)

    def clear_schematic_bindings(self):
        """移除上次网表安装的引脚别名观察器，恢复每个物理引脚独立状态。"""
        seen = set()
        for net in list(self.nets.values()) + list(self.schematic_nets.values()):
            if id(net) in seen:
                continue
            seen.add(id(net))
            net.watchers = [w for w in net.watchers if not getattr(w, "_schematic_alias", False)]
        self.schematic_pin_nets.clear()

    def _net_changed(self, key, old, new):
        n = self.nets[key]
        self.events.publish(self.sysctrl.now_ns, f"gpio.{n.name}", new)
        self.exti.on_net_edge(key[0], key[1], old, new)

    # GPIO 模型 -> MCU 驱动
    def set_mcu_output(self, port_idx, pin, level):
        self.resolved_net(port_idx, pin).set_mcu(level, (port_idx, pin))

    def set_mcu_pull(self, port_idx, pin, level):
        """设置 GPIO 内部上拉/下拉电阻的数字等效状态。"""
        self.resolved_net(port_idx, pin).set_mcu_pull((port_idx, pin), level)

    # TIM AF -> 引脚（仅当 GPIO 配置为 AF 输出时驱动网络）。
    # AF 开漏输出为高时释放线路，依赖外部上拉获得逻辑 1。
    def set_af_output(self, port_idx, pin, level):
        mode, cnf = self.gpios[port_idx].pin_cfg(pin)
        net = self.resolved_net(port_idx, pin)
        if mode != 0 and cnf in (0b10, 0b11):
            net.set_af(None if cnf == 0b11 and level == 1 else level, (port_idx, pin))
        else:
            net.set_af(None)

    def set_pin_analog(self, port_idx, pin, volts):
        self.resolved_net(port_idx, pin).mcu_analog = volts

    def mcu_pin_level(self, port_idx, pin):
        return self.resolved_net(port_idx, pin).level or 0

    def read_input(self, port_idx, pin):
        net = self.resolved_net(port_idx, pin)
        if net.level is not None:
            return net.level
        # 模拟电阻网络没有数字 level 缓存时，按 STM32F1 数字输入阈值做确定性判定。
        # VIL<=0.3*VDD 为低，VIH>=0.7*VDD 为高；中间区域按低处理（真实芯片该区未定义）。
        schematic = self.devices.get("schematic")
        voltage = schematic.mcu_pin_voltage("P" + "ABCDE"[port_idx] + str(pin)) if schematic else net.voltage()
        if voltage is not None and voltage >= 0.7 * 3.3:
            return 1
        return 0

    # ---------------- 复位 ----------------
    def reset(self):
        for p in self.all_periphs():
            p.reset()
        seen = set()
        for n in list(self.nets.values()) + list(self.schematic_nets.values()):
            if id(n) in seen:
                continue
            seen.add(id(n))
            n.mcu_level = None
            n.af_level = None
            n.mcu_outputs.clear()
            n.af_outputs.clear()
            n.mcu_pulls.clear()
            n._commit()

    # ---------------- 事件便捷 ----------------
    def publish(self, topic, data=None):
        self.events.publish(self.sysctrl.now_ns, topic, data)
