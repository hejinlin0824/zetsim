#!/usr/bin/env python3
"""zetsim 一键环境检查 + 安装（项目级，不污染系统）。

用法（任何电脑 clone 后）：
    python setup_env.py

做什么：
  1. 检查 Python ≥ 3.10，安装 Python 依赖（pip install -e .）
  2. 检查 arm-none-eabi-gcc（C 编译器），查找顺序：
       系统 PATH → 本项目 .toolchain/ → winget 默认安装目录
  3. 都没有就从 xPack GitHub 下载 GNU Arm Embedded GCC，
     解压到本项目 .toolchain/（约 500MB，已加入 .gitignore）
     —— zetsim build / 网页"保存并编译运行"会自动使用它

无网络时：按提示用 winget install Arm.GnuArmEmbeddedToolchain 装系统版即可。
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
import platform as _pl
import urllib.request

ROOT = Path(__file__).resolve().parent
TOOLCHAIN_DIR = ROOT / ".toolchain"
XPACK_REPO = "xpack-dev-tools/arm-none-eabi-gcc-xpack"


def find_gcc() -> Path | None:
    g = shutil.which("arm-none-eabi-gcc")
    if g:
        return Path(g)
    if TOOLCHAIN_DIR.exists():
        for pat in ("**/bin/arm-none-eabi-gcc.exe", "**/bin/arm-none-eabi-gcc"):
            hits = sorted(TOOLCHAIN_DIR.glob(pat))
            if hits:
                return hits[0]
    if sys.platform == "win32":
        for base in (r"C:\Program Files (x86)", r"C:\Program Files"):
            b = Path(base)
            if not b.exists():
                continue
            for d in sorted(b.glob("Arm GNU Toolchain*"), reverse=True):
                subs = sorted(d.iterdir(), reverse=True) if d.is_dir() else []
                for sub in subs:
                    cand = sub / "bin" / "arm-none-eabi-gcc.exe"
                    if cand.exists():
                        return cand
    return None


def xpack_platform() -> str | None:
    m = _pl.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "x64" if m in ("amd64", "x86_64", "x64") else None
    if not arch:
        return None
    return {"Windows": "win32", "Linux": "linux", "Darwin": "darwin"}.get(_pl.system(), None) + "-" + arch


def download_toolchain() -> Path | None:
    plat = xpack_platform()
    if not plat:
        print(f"  不支持的平台：{_pl.system()} {_pl.machine()}，请手动安装 arm-none-eabi-gcc")
        return None
    print(f"  从 xPack GitHub 下载（平台 {plat}，约 120MB，稍候）…")
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
        return find_gcc()
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
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  pip 安装失败（可能系统限制），建议：")
        print("    python -m venv .venv && .venv\\Scripts\\activate && pip install -e .")
        print("  " + r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "")
    else:
        print("✓ Python 依赖就绪")

    # 3. C 编译器
    gcc = find_gcc()
    if gcc:
        print(f"✓ arm-none-eabi-gcc：{gcc}")
        print("\n全部就绪。启动：python -m zetsim serve")
        return 0

    print("→ 未找到 arm-none-eabi-gcc，开始项目级安装（.toolchain/，不动系统）…")
    gcc = download_toolchain()
    if gcc:
        print(f"✓ arm-none-eabi-gcc：{gcc}")
        print("\n全部就绪。启动：python -m zetsim serve")
        return 0
    print("\n✗ 编译器未能自动安装。装好后重跑本脚本验证。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
