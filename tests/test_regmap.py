"""交叉验证：已实现外设模型的基址必须与官方 SVD 一致。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.board import Board
from zetsim.regmap import REGMAP

# 模型对象属性名 -> SVD 外设名
CHECKS = [
    ("rcc", "RCC"),
    ("afio", "AFIO"),
    ("exti", "EXTI"),
    ("dac", "DAC"),
    ("dma", "DMA1"),
    ("dma2", "DMA2"),
]

PIN_CHECKS = [("gpios", "GPIO{}", ["A", "B", "C", "D", "E"]),
              ("usarts", "USART{}", ["1", "2", "3"]),
              ("timers", "TIM{}", ["1", "2", "3", "4", "5", "6", "7", "8"]),
              ("adcs", "ADC{}", ["1", "2", "3"]),
              ("spis", "SPI{}", ["1", "2", "3"]),
              ("i2cs", "I2C{}", ["1", "2"])]


def _lookup(board, attr, k):
    d = getattr(board, attr)
    if attr == "gpios":
        return d["ABCDE".index(k)]
    if attr in ("usarts", "timers", "adcs", "spis", "i2cs"):
        return d[int(k)]
    return d[k]


def test_bases_match_svd():
    board = Board()
    board.reset()
    errors = []
    for attr, svd_name in CHECKS:
        obj = getattr(board, attr)
        expect = REGMAP[svd_name]["base"]
        if obj.base != expect:
            errors.append(f"{attr}: model={obj.base:#x} svd={expect:#x}")
    for attr, pattern, keys in PIN_CHECKS:
        for k in keys:
            obj = _lookup(board, attr, k)
            svd_name = pattern.format(k)
            expect = REGMAP.get(svd_name, {}).get("base")
            if expect is None:
                continue
            if obj.base != expect:
                errors.append(f"{svd_name}: model={obj.base:#x} svd={expect:#x}")
    assert not errors, "基址与 SVD 不符:\n" + "\n".join(errors)


def test_sysctrl_ppb():
    board = Board()
    board.reset()
    assert board.sysctrl.base == 0xE000E000        # PPB 起始（STK/NVIC/SCB 都在其中）
    assert REGMAP["STK"]["base"] == 0xE000E010
    assert REGMAP["NVIC"]["base"] == 0xE000E100
    assert REGMAP["SCB"]["base"] == 0xE000ED00
    assert board.sysctrl.base + 0x10 == REGMAP["STK"]["base"]


def test_key_register_offsets():
    """抽查关键寄存器偏移与模型实现一致。"""
    from zetsim.regmap import REGMAP as R
    assert R["RCC"]["regs"]["APB2ENR"][0] == 0x18
    assert R["RCC"]["regs"]["APB1ENR"][0] == 0x1C
    g = R["GPIOA"]["regs"]
    assert g["CRL"][0] == 0x00 and g["CRH"][0] == 0x04 and g["BSRR"][0] == 0x10
    u = R["USART1"]["regs"]
    assert u["SR"][0] == 0x00 and u["DR"][0] == 0x04 and u["BRR"][0] == 0x08 and u["CR1"][0] == 0x0C
    t = R["TIM2"]["regs"]
    assert t["PSC"][0] == 0x28 and t["ARR"][0] == 0x2C and t["CCR1"][0] == 0x34
    assert R["ADC1"]["regs"]["DR"][0] == 0x4C
