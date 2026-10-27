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
        self.mcu_level = None        # 推挽/开漏输出（None=不驱动）
        self.af_level = None         # 复用功能（TIM PWM 等）
        self.device_level = None     # 器件强驱动（按键）
        self.device_analog = None    # 模拟驱动（电位器）
        self.mcu_analog = None       # MCU 模拟输出（DAC）
        self.level = None            # 解析结果缓存
        self.watchers: list = []

    def _resolve(self):
        for lv in (self.mcu_level, self.af_level, self.device_level):
            if lv is not None:
                return lv
        return None

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

    def set_mcu(self, lv):
        if self.mcu_level != lv:
            self.mcu_level = lv
            self._commit()

    def set_af(self, lv):
        if self.af_level != lv:
            self.af_level = lv
            self._commit()

    def set_device(self, lv):
        if self.device_level != lv:
            self.device_level = lv
            self._commit()

    def reset_bindings(self):
        """原理图重建：清掉所有驱动与器件 watcher（保留板级 EXTI watcher）。"""
        self.mcu_level = None
        self.af_level = None
        self.device_level = None
        self.device_analog = None
        self.mcu_analog = None
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
            n.watchers.append(lambda old, new, k=net_id:
                              self.events.publish(self.sysctrl.now_ns, f"net.{k}", new))
            self.schematic_nets[net_id] = n
        return self.schematic_nets[net_id]

    def _net_changed(self, key, old, new):
        n = self.nets[key]
        self.events.publish(self.sysctrl.now_ns, f"gpio.{n.name}", new)
        self.exti.on_net_edge(key[0], key[1], old, new)

    # GPIO 模型 -> MCU 驱动
    def set_mcu_output(self, port_idx, pin, level):
        self.net(port_idx, pin).set_mcu(level)

    # TIM AF -> 引脚（仅当 GPIO 配置为 AF 输出时驱动网络）
    def set_af_output(self, port_idx, pin, level):
        mode, cnf = self.gpios[port_idx].pin_cfg(pin)
        if mode != 0 and cnf == 0b10:
            self.net(port_idx, pin).set_af(level)
        else:
            self.net(port_idx, pin).set_af(None)

    def set_pin_analog(self, port_idx, pin, volts):
        self.net(port_idx, pin).mcu_analog = volts

    def mcu_pin_level(self, port_idx, pin):
        return self.net(port_idx, pin).level or 0

    def read_input(self, port_idx, pin):
        return self.net(port_idx, pin).level or 0

    # ---------------- 复位 ----------------
    def reset(self):
        for p in self.all_periphs():
            p.reset()
        for n in self.nets.values():
            n.mcu_level = None
            n.af_level = None
            n._commit()

    # ---------------- 事件便捷 ----------------
    def publish(self, topic, data=None):
        self.events.publish(self.sysctrl.now_ns, topic, data)
