"""SVD -> 寄存器表生成器。

用法: python tools/svd_gen.py [firmware/STM32F103.svd]
产出:
  zetsim/regmap.py      —— 机器可读表（外设名 -> 基址 + 寄存器偏移）
  docs/registers.md     —— 人读速查表
数据源: modm-io/cmsis-svd-stm32 (Apache-2.0)
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse(svd_path: Path):
    root = ET.fromstring(svd_path.read_text(encoding="utf-8"))
    out = {}
    for p in root.findall(".//peripheral"):
        name = p.findtext("name")
        base = int(p.findtext("baseAddress"), 0)
        regs = {}
        for r in p.findall("./registers/register"):
            rn = r.findtext("name")
            off = int(r.findtext("addressOffset"), 0)
            desc = (r.findtext("description") or "").strip().split("\n")[0][:60]
            regs[rn] = (off, desc)
        derived = p.findtext("derivedFrom")
        if derived and not regs:
            regs = dict(out.get(derived, {}).get("regs", {})) if isinstance(out.get(derived), dict) else {}
        out[name] = {"base": base, "regs": regs}
    return out


def gen_py(table: dict) -> str:
    lines = ['"""自动生成（tools/svd_gen.py）——STM32F103 寄存器地图。勿手改。"""', "", "REGMAP = {"]
    for name in sorted(table):
        info = table[name]
        lines.append(f"    {name!r}: {{'base': {info['base']:#010x}, 'regs': {{")
        for rn, (off, desc) in sorted(info["regs"].items(), key=lambda kv: kv[1][0]):
            lines.append(f"        {rn!r}: ({off}, {desc!r}),")
        lines.append("    }},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def gen_md(table: dict) -> str:
    lines = ["# STM32F103 寄存器速查（SVD 自动生成）", "",
             "来源: modm-io/cmsis-svd-stm32 (Apache-2.0)，经 `tools/svd_gen.py` 生成。", ""]
    for name in sorted(table):
        info = table[name]
        lines.append(f"## {name} — `{info['base']:#010x}`")
        lines.append("")
        lines.append("| 寄存器 | 偏移 | 说明 |")
        lines.append("|---|---|---|")
        for rn, (off, desc) in sorted(info["regs"].items(), key=lambda kv: kv[1][0]):
            lines.append(f"| {rn} | `{off:#06x}` | {desc} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    svd = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "firmware" / "STM32F103.svd"
    table = parse(svd)
    (ROOT / "zetsim" / "regmap.py").write_text(gen_py(table), encoding="utf-8")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "registers.md").write_text(gen_md(table), encoding="utf-8")
    print(f"生成 zetsim/regmap.py 与 docs/registers.md（{len(table)} 外设）")


if __name__ == "__main__":
    main()
