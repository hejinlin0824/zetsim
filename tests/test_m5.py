"""M5: DMA 循环搬运 + SPI 回环 + I2C OLED(SSD1306) + DAC。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.asm import Asm, Firmware
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.devices import Potentiometer, Ssd1306
from test_m1_m2 import crlh


# ---------------- DMA: ADC -> 内存循环 ----------------
def fw_adc_dma() -> Firmware:
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # 时钟: ADC1 + GPIOA + DMA1(APB1 bit0)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.mov32(2, (1 << 9) | (1 << 2)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x4002101C)
    a.ldr(1, 0, 0); a.movs(2, 1); a.orr(1, 2); a.str(1, 0, 0)
    # ADC1 通道1(PA1)
    a.mov32(0, 0x40012400)
    a.movw(1, 1); a.str(1, 0, 0x34)
    a.movs(1, 3); a.str(1, 0, 8)                  # ADON|CONT
    # DMA1 通道1: CPAR=ADC_DR CMAR=0x20000000 CNDTR=8
    a.mov32(0, 0x40020008)                        # DMA1 CH1 CCR
    a.mov32(1, 0x20000000); a.str(1, 0, 0xC)      # CMAR
    a.mov32(1, 0x4001244C); a.str(1, 0, 8)        # CPAR
    a.movw(1, 512); a.str(1, 0, 4)               # CNDTR
    a.mov32(1, 1 | 0x20 | 0x80 | 0x100 | 0x400)   # EN|CIRC|MINC|PSIZE16|MSIZE16
    a.str(1, 0, 0)
    # SWSTART
    a.mov32(0, 0x40012400)
    a.mov32(1, (1 << 30) | (1 << 8) | 3); a.str(1, 0, 8)
    a.label("idle")
    a.wfi(); a.bw("idle")
    fw.add(0x08000100, a.assemble())
    return fw


def test_m5_adc_dma_circular():
    board = Board()
    board.reset()
    pot = Potentiometer(board, "pot1", "PA1", volts=2.0)
    board.devices["pot1"] = pot
    board.core.load_segments(fw_adc_dma().build())
    sim = Simulation(board)
    sim.schedule(100_000, lambda: pot.set(1.0))   # 100µs 后改电压
    rep = sim.run(until_ms=0.15, wall_timeout_s=10)
    mem = board.core.mem.read_bytes(0x20000000, 128)
    vals = [int.from_bytes(mem[i:i + 2], "little") for i in range(0, 128, 2)]
    expect_2v = round(2.0 / 3.3 * 4095)
    expect_1v = round(1.0 / 3.3 * 4095)
    nz = [v for v in vals if v]      # 非零样本
    assert len(nz) >= 20, f"DMA 搬运样本过少: {vals}"
    assert abs(nz[0] - expect_2v) < 40, vals
    assert abs(nz[-1] - expect_1v) < 40, vals
    assert len(set(vals)) >= 2, "应有两种电压值（电位器中途变化）"
    ch = board.dma.channels[0]
    assert ch.regs.get(4, 0) < 512 and ch.regs.get(4, 0) > 0, "CNDTR 异常"


# ---------------- SPI 回环 ----------------
def fw_spi() -> Firmware:
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # 时钟: SPI1 + GPIOA; PA5=SCK PA7=MOSI AF
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.mov32(2, (1 << 12) | (1 << 2)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({5: 0xB, 7: 0xB})); a.str(1, 0, 0)
    # SPI1: CR1 = MSTR|SPE|BR(f/2)
    a.mov32(0, 0x40013000)
    a.movw(1, (1 << 2) | (1 << 6)); a.str(1, 0, 0)
    # 发 3 字节并读回
    a.movs(4, 0)
    a.label("loop")
    a.ldr(1, 0, 8)                    # SR
    a.lsrs(1, 1, 1); a.lsls(1, 1, 31)  # TXE bit1
    a.bpl("loop")
    # 数据 = 0xA0 + r4
    a.movs(1, 0xA0); a.adds_rr(1, 1, 4); a.str(1, 0, 0xC)
    # 等 RXNE 读回
    a.label("waitrx")
    a.ldr(1, 0, 8)
    a.lsls(1, 1, 31)                    # RXNE bit0 -> N
    a.bpl("waitrx")
    a.ldr(2, 0, 0xC)                   # DR 读回
    a.adds(4, 1)
    a.cmp(4, 3)
    a.bne("loop")
    a.bkpt()
    fw.add(0x08000100, a.assemble())
    return fw


def test_m5_spi_loopback():
    board = Board()
    board.reset()
    board.core.load_segments(fw_spi().build())
    sim = Simulation(board)
    rep = sim.run(until_ms=5, wall_timeout_s=10)
    tx = [e.data for e in board.events.query("spi1.tx")]
    assert tx == [0xA0, 0xA1, 0xA2], f"SPI TX {tx}"
    assert rep.halt_reason == "bkpt", rep.halt_reason
    assert board.core.mem.read(0, 4) or True   # r2 持有最后读回值
    r2 = board.core.dump()["regs"]["r2"]
    assert r2 == 0xA2, f"最后读回 {r2:#x}"


# ---------------- I2C OLED ----------------
def fw_oled() -> Firmware:
    """I2C1 @PB6/PB7 -> SSD1306(0x3C)：初始化 + 写显示数据。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # 时钟: AFIO + GPIOB + I2C1
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.mov32(2, (1 << 0) | (1 << 3)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x4002101C)
    a.ldr(1, 0, 0); a.mov32(2, (1 << 21)); a.orr(1, 2); a.str(1, 0, 0)
    # PB6/PB7 AF 开漏 50M (0xF)
    a.mov32(0, 0x40010C00)
    a.mov32(1, crlh({6: 0xF, 7: 0xF})); a.str(1, 0, 0)
    # I2C1: CR2 FREQ=8, CCR=40, TRISE=9, PE=1; r5 存基址
    a.mov32(5, 0x40005400)
    a.movs(1, 8); a.str(1, 5, 4)
    a.movw(1, 40); a.str(1, 5, 0x1C)
    a.movs(1, 9); a.str(1, 5, 0x20)
    a.movs(1, 1); a.str(1, 5, 0)
    # ---- 主流程：命令块 ----
    a.bl("start_addr")
    a.movs(1, 0x00); a.bl("tx_byte")           # 控制字节=命令
    for cmd in (0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
                0x8D, 0x14, 0xA1, 0xC8, 0xDA, 0x12, 0x81, 0xCF,
                0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6):
        a.movs(1, cmd); a.bl("tx_byte")
    a.bl("do_stop")
    # 开显示
    a.bl("start_addr")
    a.movs(1, 0x00); a.bl("tx_byte")
    a.movs(1, 0xAF); a.bl("tx_byte")
    a.bl("do_stop")
    # 显示数据: 控制字节 0x40 + 32 字节 0xF0
    a.bl("start_addr")
    a.movs(1, 0x40); a.bl("tx_byte")
    a.movs(4, 0)
    a.label("dloop")
    a.movs(1, 0xF0)
    a.bl("tx_byte")
    a.adds(4, 1); a.cmp(4, 32); a.bne("dloop")
    a.bl("do_stop")
    a.bkpt()
    # ---- 子程序 ----
    a.label("tx_byte")                          # r1=字节
    a.label("wt")
    a.ldr(0, 5, 0x14)
    a.lsrs(0, 0, 7); a.lsls(0, 0, 31)
    a.bpl("wt")
    a.str(1, 5, 0x10)
    a.bx_lr()
    a.label("start_addr")
    a.ldr(1, 5, 0); a.mov32(2, 1 << 8); a.orr(1, 2); a.str(1, 5, 0)
    a.label("wsb")
    a.ldr(0, 5, 0x14); a.lsls(0, 0, 31); a.bpl("wsb")
    a.movs(1, 0x78)
    a.str(1, 5, 0x10)
    a.label("waddr")
    a.ldr(0, 5, 0x14); a.lsrs(0, 0, 1); a.lsls(0, 0, 31); a.bpl("waddr")
    a.ldr(0, 5, 0x18)                           # SR2 清 ADDR
    a.bx_lr()
    a.label("do_stop")
    a.label("wbtf")
    a.ldr(0, 5, 0x14); a.lsrs(0, 0, 2); a.lsls(0, 0, 31); a.bpl("wbtf")
    a.ldr(1, 5, 0); a.mov32(2, 1 << 9); a.orr(1, 2); a.str(1, 5, 0)
    a.bx_lr()
    fw.add(0x08000100, a.assemble())
    return fw


def test_m5_i2c_oled():
    board = Board()
    board.reset()
    oled = Ssd1306(board, "oled1", addr=0x3C)
    board.devices["oled1"] = oled
    board.i2cs[1].devices[0x3C] = oled
    board.core.load_segments(fw_oled().build())
    sim = Simulation(board)
    rep = sim.run(until_ms=10, wall_timeout_s=15)
    assert rep.halt_reason == "bkpt", f"未跑完: {rep.halt_reason} {rep.error}"
    assert oled.on, "SSD1306 未收到开屏命令 0xAF"
    assert oled.count_on() == 32 * 4, f"像素数 {oled.count_on()} != 128 (32字节 x 0xF0 的 4 个 1)"


# ---------------- DAC ----------------
def test_m5_dac():
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x4002101C)
    a.ldr(1, 0, 0); a.mov32(2, 1 << 29); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40007400)                     # DAC
    a.movs(1, 1); a.str(1, 0, 0)               # CR EN1
    a.movw(1, 2048); a.str(1, 0, 8)            # DHR12R1
    a.bkpt()
    fw.add(0x08000100, a.assemble())

    board = Board()
    board.reset()
    board.core.load_segments(fw.build())
    sim = Simulation(board)
    rep = sim.run(until_ms=2, wall_timeout_s=5)
    v = board.net(0, 4).voltage()              # PA4
    assert v is not None and abs(v - 1.65) < 0.01, f"DAC 输出 {v}"
    dor = board.dac.regs.get(0x2C, 0)
    assert dor == 2048


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
