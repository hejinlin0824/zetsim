"""项目编译 —— 调用 arm-none-eabi-gcc 把 C 源码编成 firmware.hex。

项目目录约定（如 projects/led_marquee/）：
    main.c         项目代码（必填）
    startup.c      复位启动（缺省用项目自带；没有则报错）
    stm32f103.h    寄存器定义
    link.ld        链接脚本
    firmware.hex   编译产物（zetsim 直接加载）
"""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_FILES = ("main.c", "startup.c", "stm32f103.h", "link.ld")   # 模板文件
PROTECTED = ("main.c", "startup.c", "link.ld")                      # 不可删除
_CFLAGS = ["-mcpu=cortex-m3", "-mthumb", "-nostdlib", "-O0", "-g",
           "-ffreestanding", "-Wall"]
_REPO = Path(__file__).resolve().parent.parent


def find_gcc() -> str | None:
    """找到 arm-none-eabi-gcc：PATH → 项目级 .toolchain/ → winget 安装目录。"""
    gcc = shutil.which("arm-none-eabi-gcc")
    if gcc:
        return gcc
    local = _REPO / ".toolchain"                    # setup_env.py 装的项目级编译器
    if local.exists():
        for pat in ("**/bin/arm-none-eabi-gcc.exe", "**/bin/arm-none-eabi-gcc"):
            hits = sorted(local.glob(pat))
            if hits:
                return str(hits[0])
    for base in (r"C:\Program Files (x86)", r"C:\Program Files"):
        p = Path(base)
        if not p.exists():
            continue
        # winget 布局：Arm GNU Toolchain arm-none-eabi\<版本>\bin\arm-none-eabi-gcc.exe
        for d in sorted(p.glob("Arm GNU Toolchain*"), reverse=True):
            for sub in sorted(d.iterdir(), reverse=True) if d.is_dir() else []:
                cand = sub / "bin" / "arm-none-eabi-gcc.exe"
                if cand.exists():
                    return str(cand)
    return None


def build_project(project_dir: str | Path) -> tuple[bool, str]:
    """编译项目 → firmware.hex。项目里所有 .c 都参与编译。返回 (成功, 编译日志)。"""
    project_dir = Path(project_dir).resolve()
    if not (project_dir / "main.c").exists():
        return False, f"目录里没有 main.c：{project_dir}"
    gcc = find_gcc()
    if not gcc:
        return False, ("未找到 arm-none-eabi-gcc（C 编译器）。安装：\n"
                       "  python setup_env.py        （推荐：项目级，不动系统）\n"
                       "  winget install Arm.GnuArmEmbeddedToolchain\n"
                       "装完重试编译即可。")
    tool_dir = Path(gcc).parent
    exe_suffix = ".exe" if os.name == "nt" else ""
    objcopy = tool_dir / ("arm-none-eabi-objcopy" + exe_suffix)
    size_tool = tool_dir / ("arm-none-eabi-size" + exe_suffix)
    srcs = sorted((str(p) for p in project_dir.glob("*.c")),
                  key=lambda p: (Path(p).name != "startup.c", p))   # startup 排最前
    elf = project_dir / "firmware.elf"
    hexf = project_dir / "firmware.hex"

    cmd = [gcc, *_CFLAGS, *srcs, "-lgcc",
           "-I", str(project_dir),
           "-T", str(project_dir / "link.ld"),
           "-Wl,--gc-sections", "-o", str(elf)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir,
                       encoding="utf-8", errors="replace")
    log = "$ arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb ...\n" + (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        return False, log

    r2 = subprocess.run([str(objcopy), "-O", "ihex", str(elf), str(hexf)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r2.returncode != 0:
        return False, log + "\n" + r2.stderr

    r3 = subprocess.run([str(size_tool), str(elf)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    size_line = [ln for ln in r3.stdout.splitlines() if ln.strip()][1] if r3.stdout else ""
    log += f"\n\n   text    data     bss\n{size_line}\n✓ 已生成 firmware.hex（可直接 zetsim serve 加载）"
    return True, log
