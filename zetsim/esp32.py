"""ESP32-S3 backend via Espressif ESP-IDF and the official Espressif QEMU fork.

This is deliberately separate from zetsim's Cortex-M3/Unicorn board. ESP32-S3
uses Xtensa LX7 and must not be loaded into the STM32 emulator.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT = _REPO / "projects" / "esp32s3_blink"
TARGET = "esp32s3"


def validate_project(project_dir: str | Path) -> Path:
    """Resolve and validate a normal ESP-IDF project directory."""
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"ESP-IDF 项目目录不存在：{project}")
    required = (
        project / "CMakeLists.txt",
        project / "main" / "CMakeLists.txt",
        project / "main" / "main.c",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(
            "这不是完整的 ESP-IDF 项目，缺少：\n  "
            + "\n  ".join(missing)
            + "\n请使用包含项目 CMakeLists.txt 与 main/main.c 的 ESP-IDF 工程目录。"
        )
    return project


def resolve_idf_command(
    env: Mapping[str, str] | None = None,
) -> tuple[list[str] | None, str | None]:
    """Return an executable idf.py command, using the IDF-managed Python when present."""
    current_env = os.environ if env is None else env
    idf_path = current_env.get("IDF_PATH")
    if idf_path:
        idf_script = Path(idf_path).expanduser() / "tools" / "idf.py"
        if not idf_script.is_file():
            return None, (
                f"检测到 IDF_PATH={idf_path}，但不存在 {idf_script}。"
                "请在 ESP-IDF 安装目录重新运行 export.ps1 / export.sh。"
            )

        python_env = current_env.get("IDF_PYTHON_ENV_PATH")
        if python_env:
            env_root = Path(python_env).expanduser()
            candidates = (
                env_root / "Scripts" / "python.exe",
                env_root / "Scripts" / "python",
                env_root / "bin" / "python",
                env_root / "bin" / "python3",
            )
            for candidate in candidates:
                if candidate.is_file():
                    return [str(candidate), str(idf_script)], None

        # An activated ESP-IDF shell puts its managed Python first in PATH.
        path_python = shutil.which("python", path=current_env.get("PATH"))
        python = path_python or sys.executable
        return [python, str(idf_script)], None

    executable = shutil.which("idf.py", path=current_env.get("PATH"))
    if executable:
        if Path(executable).suffix.lower() == ".py":
            python = shutil.which("python", path=current_env.get("PATH")) or sys.executable
            return [python, executable], None
        return [executable], None

    return None, (
        "未找到 ESP-IDF 环境。请先安装 Espressif ESP-IDF（建议 v6.1），"
        "并在当前 PowerShell 窗口运行 ESP-IDF 的 export.ps1；"
        "Linux/macOS 请 source export.sh。QEMU 运行还需要安装 qemu-xtensa。"
    )


def _prepare(
    project_dir: str | Path,
    env: Mapping[str, str] | None = None,
) -> tuple[Path | None, list[str] | None, dict[str, str] | None, str | None]:
    try:
        project = validate_project(project_dir)
    except (OSError, ValueError) as exc:
        return None, None, None, str(exc)

    current_env = dict(os.environ if env is None else env)
    current_env["IDF_TARGET"] = TARGET
    idf_command, error = resolve_idf_command(current_env)
    if error:
        return project, None, current_env, error
    return project, idf_command, current_env, None


def build_esp32_project(
    project_dir: str | Path = DEFAULT_PROJECT,
    *,
    env: Mapping[str, str] | None = None,
    runner=None,
    timeout_s: int = 1200,
) -> tuple[bool, str]:
    """Build an ESP32-S3 firmware image with idf.py. The runner hook enables unit tests."""
    project, idf_command, current_env, error = _prepare(project_dir, env)
    if error or project is None or idf_command is None or current_env is None:
        return False, error or "无法初始化 ESP-IDF 构建环境。"

    command = [*idf_command, "-C", str(project), "build"]
    display = "$ " + shlex.join(command)
    run = runner or subprocess.run
    try:
        result = run(
            command,
            cwd=str(project),
            env=current_env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        return False, f"{display}\nESP-IDF 构建超过 {timeout_s}s 超时。\n{output}"
    except OSError as exc:
        return False, f"{display}\n无法启动 ESP-IDF：{exc}"

    output = result.stdout or ""
    if result.returncode != 0:
        return False, f"{display}\n{output}".rstrip()
    return True, f"{display}\n{output}".rstrip()


def run_esp32_project(
    project_dir: str | Path = DEFAULT_PROJECT,
    *,
    graphics: bool = False,
    env: Mapping[str, str] | None = None,
    runner=None,
) -> int:
    """Build and run an ESP-IDF app in Espressif QEMU, with the UART monitor attached."""
    project, idf_command, current_env, error = _prepare(project_dir, env)
    if error or project is None or idf_command is None or current_env is None:
        print(error or "无法初始化 ESP-IDF 运行环境。", file=sys.stderr)
        return 2

    command = [*idf_command, "-C", str(project), "qemu"]
    if graphics:
        command.append("--graphics")
    command.append("monitor")
    print("$ " + shlex.join(command), flush=True)
    run = runner or subprocess.run
    try:
        result = run(command, cwd=str(project), env=current_env)
    except OSError as exc:
        print(f"无法启动 ESP-IDF/QEMU：{exc}", file=sys.stderr)
        return 2
    return int(result.returncode)
