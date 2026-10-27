"""GPIO A-E（0x40010800+0x400*n）— CRL/CRH/IDR/ODR/BSRR/BRR/LCKR。"""
from __future__ import annotations
from . import Peripheral


class Gpio(Peripheral):
    name = "GPIO?"
    size = 0x28
    RESET_IDR = 0x0000     # 输入随网络

    def __init__(self, port_idx: int):
        super().__init__()
        self.port_idx = port_idx
        self.name = f"GPIO{'ABCDE'[port_idx]}"
        self.base = 0x40010800 + 0x400 * port_idx

    # ---- 引脚配置解析 ----
    def pin_cfg(self, pin: int):
        off = 0x00 if pin < 8 else 0x04
        v = self.regs.get(off, 0x44444444)          # 复位值：浮空输入
        shift = (pin % 8) * 4
        nib = (v >> shift) & 0xF
        return nib & 3, (nib >> 2) & 3              # MODE, CNF

    def _odr(self) -> int:
        return self.regs.get(0x0C, 0)

    def read(self, off, size):
        if off == 0x08:                              # IDR：实时合成
            v = 0
            for pin in range(16):
                mode, cnf = self.pin_cfg(pin)
                if mode != 0:                        # 输出模式：回读自身电平
                    if self.board:
                        lv = self.board.mcu_pin_level(self.port_idx, pin)
                        if lv:
                            v |= 1 << pin
                else:                                # 输入：读网络
                    if self.board:
                        lv = self.board.read_input(self.port_idx, pin)
                        if lv:
                            v |= 1 << pin
            return v
        return super().read(off, size)

    def write(self, off, size, value):
        if off == 0x10:                              # BSRR
            odr = self._odr()
            odr |= value & 0xFFFF
            odr &= ~(value >> 16) & 0xFFFF
            self.regs[0x0C] = odr & 0xFFFF
            self._apply_outputs(changed=(value & 0xFFFF) | ((value >> 16) & 0xFFFF))
            return
        if off == 0x14:                              # BRR
            odr = self._odr() & ~value
            self.regs[0x0C] = odr & 0xFFFF
            self._apply_outputs(changed=value & 0xFFFF)
            return
        if off == 0x0C:                              # ODR
            super().write(off, size, value)
            self._apply_outputs(changed=0xFFFF)
            return
        if off in (0x00, 0x04):                      # CRL/CRH：重应用
            super().write(off, size, value)
            self._apply_outputs(changed=0xFFFF)
            return
        super().write(off, size, value)

    def _apply_outputs(self, changed: int):
        for pin in range(16):
            if not (changed >> pin) & 1:
                continue
            mode, cnf = self.pin_cfg(pin)
            if self.board is None:
                continue
            if mode != 0 and cnf != 0b10:            # 通用输出（AF 由 TIM 驱动）
                odr_bit = (self._odr() >> pin) & 1
                if cnf == 0b01:                      # 开漏：输出 0 拉低，1 悬空
                    self.board.set_mcu_output(self.port_idx, pin, 0 if odr_bit == 0 else None)
                else:                                # 推挽
                    self.board.set_mcu_output(self.port_idx, pin, odr_bit)
            else:
                self.board.set_mcu_output(self.port_idx, pin, None)
