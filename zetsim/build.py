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
_TARGET_FLAGS = ["-mcpu=cortex-m3", "-mthumb"]
_CFLAGS = [*_TARGET_FLAGS, "-nostdlib", "-O0", "-g", "-ffreestanding", "-Wall"]
_REPO = Path(__file__).resolve().parent.parent


def _query_libgcc(gcc: str) -> tuple[str | None, str]:
    """Ask GCC for the runtime archive selected for Cortex-M3 Thumb and verify it exists.

    Use the compiler's own multilib selection rather than asking ld to resolve -lgcc.
    This also lets us report a damaged/incomplete toolchain before the linker emits a
    less actionable "cannot find -lgcc" message.
    """
    try:
        result = subprocess.run(
            [gcc, *_TARGET_FLAGS, "-print-libgcc-file-name"],
            capture_output=True, text=True, errors="replace", timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)

    reported = result.stdout.strip().strip('"')
    if result.returncode != 0 or not reported:
        detail = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        return None, detail

    archive = Path(reported)
    if not archive.is_absolute():
        archive = Path(gcc).resolve().parent / archive
    if not archive.is_file():
        return None, reported
    return str(archive.resolve()), reported


def find_gcc() -> str | None:
    """找到 arm-none-eabi-gcc：PATH → 项目级 .toolchain/ → winget 安装目录。"""
    candidates: list[str] = []
    system = shutil.which("arm-none-eabi-gcc")
    if system:
        candidates.append(system)

    local = _REPO / ".toolchain"
    if local.exists():
        for pat in ("**/bin/arm-none-eabi-gcc.exe", "**/bin/arm-none-eabi-gcc"):
            candidates.extend(str(path) for path in sorted(local.glob(pat)))

    for base in (r"C:\Program Files (x86)", r"C:\Program Files"):
        root = Path(base)
        if not root.exists():
            continue
        for directory in sorted(root.glob("Arm GNU Toolchain*"), reverse=True):
            for sub in sorted(directory.iterdir(), reverse=True) if directory.is_dir() else []:
                candidate = sub / "bin" / "arm-none-eabi-gcc.exe"
                if candidate.exists():
                    candidates.append(str(candidate))

    seen: set[str] = set()
    first_candidate: str | None = None
    for gcc in candidates:
        normalized = os.path.normcase(os.path.abspath(gcc))
        if normalized in seen:
            continue
        seen.add(normalized)
        if first_candidate is None:
            first_candidate = gcc
        libgcc, _reported = _query_libgcc(gcc)
        if libgcc:
            return gcc
    # Keep one discovered compiler when every candidate lacks libgcc so build_project
    # can report the exact path instead of only saying no toolchain was found.
    return first_candidate


def build_project(project_dir: str | Path) -> tuple[bool, str]:
    """编译项目 → firmware.hex。项目里所有 .c 都参与编译。返回 (成功, 编译日志)。"""
    project_dir = Path(project_dir).resolve()
    if not (project_dir / "main.c").exists():
        return False, f"目录里没有 main.c：{project_dir}"
    gcc = find_gcc()
    if not gcc:
        return False, ("未找到可用的 arm-none-eabi-gcc 工具链（编译器或 libgcc 运行库缺失）。安装/检查：\n"
                       "  python setup_env.py        （推荐：项目级，不动系统）\n"
                       "  winget install Arm.GnuArmEmbeddedToolchain\n"
                       "若编译器已经存在，请运行 arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -print-libgcc-file-name，\n"
                       "并检查它输出的 libgcc.a 是否真实存在。必要时重新安装完整工具链。")

    # Resolve libgcc from the selected multilib explicitly. Some Windows toolchain
    # installs fail to expose its directory to ld's -lgcc lookup even when the
    # compiler can identify the archive. Passing the actual archive path avoids
    # depending on implicit -L search paths.
    libgcc, reported = _query_libgcc(gcc)
    if not libgcc:
        return False, (
            f"工具链运行库缺失：{gcc}\n"
            f"GCC 报告的 libgcc 路径：{reported or '(无输出)'}\n"
            "该工具链可能安装不完整，不能完成裸机链接。请运行 python setup_env.py 重新检查，"
            "或安装完整的 Arm GNU Toolchain。\n"
            "如果仓库路径包含中文/特殊字符，请将项目放到纯英文路径（例如 E:\\codebase\\zetsim）后重试。"
        )

    tool_dir = Path(gcc).parent
    exe_suffix = ".exe" if os.name == "nt" else ""
    objcopy = tool_dir / ("arm-none-eabi-objcopy" + exe_suffix)
    size_tool = tool_dir / ("arm-none-eabi-size" + exe_suffix)
    srcs = sorted((str(p) for p in project_dir.glob("*.c")),
                  key=lambda p: (Path(p).name != "startup.c", p))   # startup 排最前
    elf = project_dir / "firmware.elf"
    hexf = project_dir / "firmware.hex"

    device_include = _REPO / "third_party" / "cmsis-device-f1" / "Include"
    core_include = _REPO / "third_party" / "CMSIS_5" / "CMSIS" / "Core" / "Include"
    hal_root = _REPO / "third_party" / "stm32f1xx-hal-driver"
    hal_include = hal_root / "Inc"
    hal_source_dir = hal_root / "Src"
    hal_project = (project_dir / "stm32f1xx_hal_conf.h").is_file()
    # Only HAL-enabled projects link the official driver code; register lessons
    # remain on their previous, smaller build path.
    hal_source_names = (
        "stm32f1xx_hal.c",
        "stm32f1xx_hal_cortex.c",
        "stm32f1xx_hal_gpio.c",
    )
    hal_sources = [hal_source_dir / name for name in hal_source_names]
    system_source = _REPO / "third_party" / "cmsis-device-f1" / "Source" / "Templates" / "system_stm32f1xx.c"
    required_files = (
        device_include / "stm32f1xx.h",
        device_include / "stm32f103xe.h",
        device_include / "system_stm32f1xx.h",
        core_include / "core_cm3.h",
        core_include / "cmsis_compiler.h",
        core_include / "cmsis_gcc.h",
        core_include / "cmsis_version.h",
        core_include / "mpu_armv7.h",
    )
    if hal_project:
        required_files += (
            hal_include / "stm32f1xx_hal.h",
            hal_include / "stm32f1xx_hal_def.h",
            hal_include / "stm32f1xx_hal_gpio.h",
            hal_include / "stm32f1xx_hal_gpio_ex.h",
            hal_include / "stm32f1xx_hal_cortex.h",
            hal_include / "stm32f1xx_hal_flash.h",
            hal_include / "stm32f1xx_hal_rcc.h",
            hal_include / "stm32f1xx_hal_rcc_ex.h",
            system_source,
            *hal_sources,
        )
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        return False, (
            "STM32 官方 CMSIS/HAL 文件缺失，无法构建教学项目：\n  "
            + "\n  ".join(missing_files)
            + "\n请确认 third_party/ 目录完整，或重新拉取 DEV。"
        )

    if hal_project:
        srcs.extend(str(path) for path in (system_source, *hal_sources))

    cmd = [gcc, *_CFLAGS]
    if hal_project:
        cmd += ["-DSTM32F103xE", "-DUSE_HAL_DRIVER",
                "-ffunction-sections", "-fdata-sections"]
    cmd += ["-I", str(project_dir),
            "-I", str(device_include),
            "-I", str(core_include)]
    if hal_project:
        cmd += ["-I", str(hal_include)]
    cmd += [*srcs, libgcc,
            "-T", str(project_dir / "link.ld"),
            "-Wl,--gc-sections", "-o", str(elf)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", cwd=project_dir)
    log = "$ arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb ...\n" + (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        return False, log

    r2 = subprocess.run([str(objcopy), "-O", "ihex", str(elf), str(hexf)],
                        capture_output=True, text=True, errors="replace", cwd=project_dir)
    if r2.returncode != 0:
        return False, log + "\n" + r2.stderr

    r3 = subprocess.run([str(size_tool), str(elf)],
                        capture_output=True, text=True, errors="replace", cwd=project_dir)
    size_line = [ln for ln in r3.stdout.splitlines() if ln.strip()][1] if r3.stdout else ""
    log += f"\n\n   text    data     bss\n{size_line}\n✓ 已生成 firmware.hex（可直接 zetsim serve 加载）"
    return True, log
