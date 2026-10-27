"""生成演示固件 .hex 资产到 firmware/ 目录（供 CLI 与 Web 仪表盘使用）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pathlib import Path

from zetsim.asm import Asm, Firmware

OUT = Path(__file__).parent.parent / "firmware"


def crlh(values, default=0x4):
    v = 0
    for pin in range(16):
        v |= values.get(pin, default) << (pin * 4)
    return v


def fw_hello():
    """USART1 打印 + 回显（RX 中断回发）。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.mov32(2, (1 << 14) | (1 << 2)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010804); a.mov32(1, crlh({9: 0xB, 10: 0x4})); a.str(1, 0, 0)
    a.mov32(0, 0x40013800)
    a.movw(1, 0x0457); a.str(1, 0, 8)
    a.mov32(1, 0x202C); a.str(1, 0, 0x0C)          # UE|TE|RE|RXNEIE
    a.mov32(0, 0xE000E104); a.mov32(1, 1 << (37 - 32)); a.str(1, 0, 0)  # ISER1 |= 1<<5 (USART1=IRQ37)
    # 发送问候（恢复 r0=USART1 基址）
    a.mov32(0, 0x40013800)
    a.mov32(2, 0x08000200)
    a.label("next")
    a.ldr(1, 0, 0); a.lsrs(1, 1, 7); a.lsls(1, 1, 31); a.bpl("next")
    a.ldrb(3, 2, 0); a.cmp(3, 0); a.beq("idle")
    a.str(3, 0, 4); a.adds(2, 1); a.bw("next")
    a.label("idle")
    a.wfi(); a.bw("idle")
    h = Asm(0x08000180)                              # USART1 IRQ(37): 回显
    h.ldr(1, 0, 0)                                   # SR
    h.lsls(1, 1, 27)                                 # RXNE(bit5) -> bit... 简化: 直接读 DR
    h.mov32(0, 0x40013800)
    h.ldr(3, 0, 4)                                   # 读 DR 清 RXNE
    a2 = Asm(0x08000180)
    a2.mov32(0, 0x40013800)
    a2.ldr(3, 0, 4)                                  # 读 DR（清 RXNE）
    a2.label("wtx")
    a2.ldr(1, 0, 0); a2.lsrs(1, 1, 7); a2.lsls(1, 1, 31); a2.bpl("wtx")
    a2.str(3, 0, 4)
    a2.bx_lr()
    msg = Asm(0x08000200)
    msg.asciz("zetsim ready.\r\nType anything:\r\n")
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000180, a2.assemble())
    fw.add(0x08000200, msg.assemble())
    fw.vector(16 + 37, 0x08000180)   # USART1=IRQ37 -> 异常53
    return fw


def fw_blink():
    """SysTick 1ms 翻转 PA5（LED 呼吸般的闪烁）。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, 4); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800); a.mov32(1, crlh({5: 0x2})); a.str(1, 0, 0)
    a.mov32(0, 0xE000E010)
    a.mov32(1, 2_000_000 - 1); a.str(1, 0, 4)         # 250ms @8MHz -> 肉眼可见的 2Hz 闪烁
    a.movs(1, 0); a.str(1, 0, 8)
    a.movs(1, 7); a.str(1, 0, 0)
    a.label("idle")
    a.wfi(); a.bw("idle")
    h = Asm(0x08000180)
    h.mov32(0, 0x4001080C)
    h.ldr(1, 0, 0); h.movs(2, 0x20); h.eor(1, 2); h.str(1, 0, 0)
    h.bx_lr()
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000180, h.assemble())
    fw.vector(15, 0x08000180)
    return fw


def fw_button():
    """PA0 按键 EXTI0 翻转 PA5。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, 5); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800); a.mov32(1, crlh({5: 0x2})); a.str(1, 0, 0)
    a.mov32(0, 0x40010400); a.movs(1, 1); a.str(1, 0, 0); a.str(1, 0, 8)
    a.mov32(0, 0xE000E100); a.mov32(1, 1 << 6); a.str(1, 0, 0)
    a.label("idle")
    a.wfi(); a.bw("idle")
    h = Asm(0x08000180)
    h.mov32(0, 0x4001080C)
    h.ldr(1, 0, 0); h.movs(2, 0x20); h.eor(1, 2); h.str(1, 0, 0)
    h.mov32(0, 0x40010414); h.movs(1, 1); h.str(1, 0, 0)
    h.bx_lr()
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000180, h.assemble())
    fw.vector(22, 0x08000180)
    return fw


def fw_pwm_adc():
    """TIM2 PA0 PWM 10kHz 30% + ADC1(PA1 电位器) 连续转换 + UART 打印 DR。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x4002101C)
    a.ldr(1, 0, 0); a.movs(2, 1); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.mov32(2, (1 << 14) | (1 << 9) | (1 << 2)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800); a.mov32(1, crlh({0: 0xB, 9: 0xB})); a.str(1, 0, 0)
    # TIM2 PWM
    a.mov32(0, 0x40000000)
    a.movw(1, 7); a.str(1, 0, 0x28)
    a.movw(1, 99); a.str(1, 0, 0x2C)
    a.movw(1, 30); a.str(1, 0, 0x34)
    a.movw(1, 0x60); a.str(1, 0, 0x18)
    a.movw(1, 1); a.str(1, 0, 0x20)
    a.movw(1, 1); a.str(1, 0, 0x00)
    # USART1
    a.mov32(0, 0x40013800)
    a.movw(1, 0x0457); a.str(1, 0, 8)
    a.movw(1, 0x0008); a.str(1, 0, 0x0C)
    # ADC1 连续
    a.mov32(0, 0x40012400)
    a.movw(1, 1); a.str(1, 0, 0x34)
    a.movs(1, 3); a.str(1, 0, 8)
    a.mov32(1, (1 << 30) | 3); a.str(1, 0, 8)
    # 循环: 每 ~100ms 打印 ADC 高字节字符
    a.label("idle")
    a.wfi(); a.bw("idle")
    msg = Asm(0x08000200)
    msg.asciz("pwm+adc\r\n")
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000200, msg.assemble())
    return fw


def main():
    OUT.mkdir(exist_ok=True)
    for name, fw in [("hello_echo.hex", fw_hello()),
                     ("blink.hex", fw_blink()),
                     ("button_exti.hex", fw_button()),
                     ("pwm_adc.hex", fw_pwm_adc())]:
        path = OUT / name
        path.write_text(fw.to_intel_hex(), encoding="ascii")
        print(f"生成 {path}  ({path.stat().st_size} 字节)")


if __name__ == "__main__":
    main()
