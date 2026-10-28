#!/usr/bin/env python3
"""zetsim 一键环境检查 + 安装（项目级，不污染系统）。

用法（任何电脑 clone 后）：
    python setup_env.py

做什么：
  1. 检查 Python ≥ 3.10，安装 Python 依赖（pip install -e .）
  2. 检查可完成裸机链接的 arm-none-eabi-gcc（不仅检查 gcc.exe，还要确认 libgcc.a 存在）
  3. 都没有就从 xPack GitHub 下载 GNU Arm Embedded GCC，解压到项目内 .toolchain/
     —— zetsim build / 网页"保存并编译运行"会自动使用它

无网络时：按提示用 winget install Arm.GnuArmEmbeddedToolchain（Windows）装系统版即可。
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
import platform as _pl
import urllib.request

ROOT = Path(__file__).resolve().parent
PROJECT_TOOLCHAIN_DIR = ROOT / ".toolchain"
XPACK_REPO = "xpack-dev-tools/arm-none-eabi-gcc-xpack"
TARGET_FLAGS = ("-mcpu=cortex-m3", "-mthumb")
TOOLCHAIN_FAILURES: list[str] = []


def preferred_toolchain_dir(root: Path | None = None) -> Path:
    """Keep the Windows toolchain outside a non-ASCII checkout path.

    Some Windows GNU binutils builds mishandle non-ASCII prefixes while searching
    their bundled runtime libraries. ZETSIM_TOOLCHAIN_DIR remains an explicit override.
    """
    override = os.environ.get("ZETSIM_TOOLCHAIN_DIR")
    if override:
        return Path(override).expanduser()
    project_root = root or ROOT
    if sys.platform == "win32" and not str(project_root).isascii():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidate = Path(local_app_data) / "zetsim" / "toolchain"
            if str(candidate).isascii():
                return candidate
    return project_root / ".toolchain"


TOOLCHAIN_DIR = preferred_toolchain_dir()


def _libgcc_path(gcc: Path) -> Path | None:
    """Return the compiler-selected Cortex-M3 libgcc archive only when it exists."""
    try:
        result = subprocess.run(
            [str(gcc), *TARGET_FLAGS, "-print-libgcc-file-name"],
            capture_output=True, text=True, errors="replace", timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    reported = result.stdout.strip().strip('"')
    if result.returncode != 0 or not reported:
        return None
    archive = Path(reported)
    if not archive.is_absolute():
        archive = gcc.resolve().parent / archive
    return archive.resolve() if archive.is_file() else None


def _gcc_candidates():
    """Yield installed compiler candidates in preferred search order."""
    seen: set[str] = set()

    def add(candidate: Path):
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if key not in seen and candidate.is_file():
            seen.add(key)
            return candidate
        return None

    from_path = shutil.which("arm-none-eabi-gcc")
    if from_path:
        candidate = add(Path(from_path))
        if candidate:
            yield candidate

    roots = [TOOLCHAIN_DIR, PROJECT_TOOLCHAIN_DIR]
    for root in dict.fromkeys(roots):
        if root.exists():
            for pat in ("**/bin/arm-none-eabi-gcc.exe", "**/bin/arm-none-eabi-gcc"):
                for path in sorted(root.glob(pat)):
                    candidate = add(path)
                    if candidate:
                        yield candidate

    if sys.platform == "win32":
        for base in (r"C:\Program Files (x86)", r"C:\Program Files"):
            root = Path(base)
            if not root.exists():
                continue
            for directory in sorted(root.glob("Arm GNU Toolchain*"), reverse=True):
                for sub in sorted(directory.iterdir(), reverse=True) if directory.is_dir() else []:
                    candidate = add(sub / "bin" / "arm-none-eabi-gcc.exe")
                    if candidate:
                        yield candidate


def _link_smoke_test(gcc: Path) -> tuple[bool, str]:
    """Actually link a tiny Cortex-M3 image; a visible libgcc.a alone is not enough."""
    libgcc = _libgcc_path(gcc)
    if not libgcc:
        return False, "GCC 没有返回存在的 libgcc.a"
    try:
        with tempfile.TemporaryDirectory(prefix="zetsim-arm-link-check-") as tmp:
            work = Path(tmp)
            source = work / "probe.c"
            script = work / "probe.ld"
            output = work / "probe.elf"
            source.write_text("void Reset_Handler(void) { for (;;) {} }\n", encoding="ascii")
            script.write_text(
                "ENTRY(Reset_Handler)\n"
                "SECTIONS { . = 0x08000000; .text : { *(.text*) *(.rodata*) } "
                ".data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }\n",
                encoding="ascii",
            )
            command = [
                str(gcc), *TARGET_FLAGS, "-nostdlib", "-ffreestanding", "-O0",
                "-L", str(libgcc.parent), str(source), str(libgcc),
                "-Wl,-T," + str(script), "-o", str(output),
            ]
            result = subprocess.run(
                command, cwd=work, capture_output=True, text=True,
                errors="replace", timeout=30,
            )
            detail = (result.stderr or result.stdout).strip()
            if result.returncode != 0 or not output.is_file():
                return False, detail or f"链接探测退出码 {result.returncode}"
            return True, "链接探测成功"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def find_gcc() -> Path | None:
    """Find a compiler that has libgcc and can actually link a Cortex-M3 probe."""
    TOOLCHAIN_FAILURES.clear()
    for gcc in _gcc_candidates():
        libgcc = _libgcc_path(gcc)
        if not libgcc:
            continue
        ok, detail = _link_smoke_test(gcc)
        if ok:
            return gcc
        TOOLCHAIN_FAILURES.append(f"{gcc}\n  libgcc: {libgcc}\n  链接探测失败: {detail}")
    return None


def xpack_platform() -> str | None:
    m = _pl.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "x64" if m in ("amd64", "x86_64", "x64") else None
    if not arch:
        return None
    return { "Windows": "win32", "Linux": "linux", "Darwin": "darwin"}.get(_pl.system(), None) + "-" + arch


def download_toolchain() -> Path | None:
    plat = xpack_platform()
    if not plat:
        print(f"  不支持的平台：{_pl.system()} {_pl.machine()}，请手动安装 arm-none-eabi-gcc")
        return None
    print(f"  从 xPack GitHub 下载（平台 {plat}，约 300MB，稍候）…")
    try:
        with urllib.request.urlopen(
                f"https://api.github.com/repos/{XPACK_REPO}/releases/latest", timeout=30) as r:
            rel = json.loads(r.read().decode())
        asset = next((a for a in rel["assets"] if plat in a["name"]
                      and a["name"].endswith((".zip", ".tar.gz"))), None)
        if not asset:
            print(f"  最新版 {rel['tag_name']} 没有 {plat} 的包，请手动安装")
            return None
        print(f"  下载 {asset['name']} …")
        arc = ROOT / asset["name"]
        urllib.request.urlretrieve(asset["browser_download_url"], arc)
        print("  解压到 .toolchain/ …")
        TOOLCHAIN_DIR.mkdir(exist_ok=True)
        if arc.suffix == ".zip":
            with zipfile.ZipFile(arc) as z:
                z.extractall(TOOLCHAIN_DIR)
        else:
            with tarfile.open(arc) as t:
                t.extractall(TOOLCHAIN_DIR)
        arc.unlink()
        gcc = find_gcc()
        if gcc:
            return gcc
        print("  下载包中没有找到可用的 Cortex-M3 libgcc.a，工具链完整性检查失败。")
        print("  请改用完整的 Arm GNU Toolchain，或检查 .toolchain/ 是否解压完整。")
        return None
    except Exception as e:
        print(f"  下载失败：{e}")
        print("  备选：winget install Arm.GnuArmEmbeddedToolchain（Windows，装到系统）")
        return None


def main() -> int:
    print("== zetsim 环境检查 ==")
    # 1. Python
    if sys.version_info < (3, 10):
        print(f"✗ Python {sys.version.split()[0]} < 3.10，请先升级 Python")
        return 1
    print(f"✓ Python {sys.version.split()[0]}")

    # 2. Python 依赖
    print("→ 安装 Python 依赖（pip install -e .）…")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("  pip 安装失败（可能系统限制），建议：")
        print("    python -m venv .venv && .venv\\Scripts\\activate && pip install -e .")
        print("  " + r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "")
    else:
        print("✓ Python 依赖就绪")

    # 3. C toolchain and runtime archive
    gcc = find_gcc()
    if gcc:
        libgcc = _libgcc_path(gcc)
        print(f"✓ arm-none-eabi-gcc：{gcc}")
        print(f"✓ libgcc runtime：{libgcc}")
        print("✓ Cortex-M3 实际链接探测：通过")
        print("\n全部就绪。启动：python -m zetsim serve")
        return 0

    print("→ 未找到通过真实链接探测的 arm-none-eabi-gcc（仅有 gcc.exe / libgcc.a 还不够）。")
    if TOOLCHAIN_FAILURES:
        print("→ 已找到工具链，但链接探测失败：")
        for failure in TOOLCHAIN_FAILURES[-3:]:
            print("  " + failure.replace("\n", "\n  "))
    print(f"→ 开始项目级安装（{TOOLCHAIN_DIR}，不动系统）…")
    gcc = download_toolchain()
    if gcc:
        libgcc = _libgcc_path(gcc)
        print(f"✓ arm-none-eabi-gcc：{gcc}")
        print(f"✓ libgcc runtime：{libgcc}")
        print("✓ Cortex-M3 实际链接探测：通过")
        print("\n全部就绪。启动：python -m zetsim serve")
        return 0
    print("\n✗ 编译工具链未能通过完整性检查。")
    print("  请确认 libgcc.a 实际存在；也可安装：winget install Arm.GnuArmEmbeddedToolchain")
    print("  若项目路径包含中文/特殊字符，请另复制到纯英文路径测试，例如 E:\\codebase\\zetsim。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
