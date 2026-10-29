"""ESP32-S3 UART telemetry parser and QEMU monitor session.

The parser reports observed behaviour, not inferred hardware support. Runtime
process launching uses a pseudo-terminal because QEMU/IDF monitor are interactive.
"""
from __future__ import annotations

from collections import deque
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from .esp32 import resolve_idf_command, validate_project

_ROM_RE = re.compile(r"ESP-ROM:esp32s3", re.IGNORECASE)
_RESET_RE = re.compile(r"rst:0x([0-9a-fA-F]+)\s*\(([^)]*)\)")
_IDF_TIME_RE = re.compile(r"\b[EWIDV] \((\d+)\)")
_GPIO_RE = re.compile(r"ZETSIM_ESP32S3_GPIO(\d+)=(0|1)")
_GPIO_READBACK_RE = re.compile(r"ZETSIM_ESP32S3_GPIO(\d+)_READBACK=(0|1)")
_GPIO_MISMATCH_RE = re.compile(r"ZETSIM_ESP32S3_GPIO(\d+)_READBACK_MISMATCH expected=(0|1) got=(0|1)")
_PLOT_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.-]{0,63})\s*:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$")


class ESP32RuntimeObserver:
    """Thread-safe bounded observer for UART0 text from an ESP32-S3 session."""

    def __init__(self, *, max_lines: int = 2000, max_samples: int = 1000):
        self.max_lines = max(20, int(max_lines))
        self.max_samples = max(10, int(max_samples))
        self._lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", threading.RLock()):
            self.started_at = time.monotonic()
            self.process_running = False
            self.exit_code: int | None = None
            self.error: str | None = None
            self._pending = ""
            self._lines: deque[str] = deque(maxlen=getattr(self, "max_lines", 2000))
            self._events: deque[dict[str, Any]] = deque(maxlen=getattr(self, "max_samples", 1000))
            self.boot_count = 0
            self.rom_seen = False
            self.reset_reason: dict[str, str] | None = None
            self.app_main_entered = False
            self.gpio_configured = False
            self.app_ready = False
            self.panic_count = 0
            self.gpio_levels: dict[str, int] = {}
            self.gpio_readback_levels: dict[str, int] = {}
            self.gpio_output_mismatch_count = 0
            self._gpio_mismatches: deque[dict[str, Any]] = deque(maxlen=getattr(self, "max_samples", 1000))
            self.plot_series: dict[str, deque[dict[str, float]]] = {}
            self.sim_time_ms: float | None = None
            self._first_sim: tuple[float, float] | None = None
            self._last_sim: tuple[float, float] | None = None
            self.last_line_at: float | None = None

    def set_process_state(
        self, running: bool, *, exit_code: int | None = None, error: str | None = None
    ) -> None:
        with self._lock:
            self.process_running = bool(running)
            self.exit_code = exit_code
            if error:
                self.error = str(error)
            self.last_line_at = time.monotonic()

    def ingest(self, chunk: str | bytes) -> None:
        """Consume an arbitrary UART chunk; line boundaries may span calls."""
        if isinstance(chunk, bytes):
            text = chunk.decode("utf-8", "replace")
        else:
            text = str(chunk)
        with self._lock:
            combined = self._pending + text.replace("\r\n", "\n").replace("\r", "\n")
            parts = combined.split("\n")
            self._pending = parts.pop()
            for line in parts:
                self._consume_line(line.rstrip())
            self.last_line_at = time.monotonic()

    def flush(self) -> None:
        with self._lock:
            if self._pending:
                self._consume_line(self._pending.rstrip())
                self._pending = ""

    def _consume_line(self, line: str) -> None:
        now = time.monotonic()
        self._lines.append(line)
        self._events.append({"wall_elapsed_ms": round((now - self.started_at) * 1000, 3), "line": line})

        if _ROM_RE.search(line):
            self.rom_seen = True
            self.boot_count += 1
            self.reset_reason = None
            self.app_main_entered = False
            self.gpio_configured = False
            self.app_ready = False
            self.sim_time_ms = None
            self._first_sim = None
            self._last_sim = None

        reset_match = _RESET_RE.search(line)
        if reset_match:
            self.reset_reason = {"code": "0x" + reset_match.group(1).lower(), "reason": reset_match.group(2).strip()}

        if "Guru Meditation Error" in line or "Unhandled exception" in line:
            self.panic_count += 1

        if "ZETSIM_ESP32S3_APP_MAIN_ENTERED" in line:
            self.app_main_entered = True
        if "ZETSIM_ESP32S3_GPIO_CONFIG_OK" in line:
            self.gpio_configured = True
        if "ZETSIM_ESP32S3_BOOT_OK" in line:
            self.app_ready = True

        gpio_match = _GPIO_RE.search(line)
        if gpio_match:
            pin, level = gpio_match.group(1), int(gpio_match.group(2))
            self.gpio_levels[pin] = level
            series = self.plot_series.setdefault(f"GPIO{pin}", deque(maxlen=self.max_samples))
            series.append({"wall_elapsed_ms": round((now - self.started_at) * 1000, 3), "value": float(level)})

        readback_match = _GPIO_READBACK_RE.search(line)
        if readback_match:
            pin, level = readback_match.group(1), int(readback_match.group(2))
            self.gpio_readback_levels[pin] = level
            series = self.plot_series.setdefault(f"GPIO{pin}_READBACK", deque(maxlen=self.max_samples))
            series.append({"wall_elapsed_ms": round((now - self.started_at) * 1000, 3), "value": float(level)})

        mismatch_match = _GPIO_MISMATCH_RE.search(line)
        if mismatch_match:
            pin, expected, got = mismatch_match.groups()
            self.gpio_output_mismatch_count += 1
            self._gpio_mismatches.append({
                "wall_elapsed_ms": round((now - self.started_at) * 1000, 3),
                "gpio": int(pin),
                "expected": int(expected),
                "got": int(got),
                "line": line,
            })

        plot_match = _PLOT_RE.match(line)
        if plot_match:
            name, raw_value = plot_match.group(1), plot_match.group(2)
            try:
                value = float(raw_value)
            except ValueError:
                value = float("nan")
            if value == value and abs(value) != float("inf"):
                series = self.plot_series.setdefault(name, deque(maxlen=self.max_samples))
                series.append({"wall_elapsed_ms": round((now - self.started_at) * 1000, 3), "value": value})

        time_match = _IDF_TIME_RE.search(line)
        if time_match:
            sim_ms = float(time_match.group(1))
            if self._last_sim is not None and sim_ms < self._last_sim[0]:
                # IDF millisecond timestamps reset at a reboot.
                self._first_sim = None
                self._last_sim = None
            self.sim_time_ms = sim_ms
            if self._first_sim is None:
                self._first_sim = (sim_ms, now)
            self._last_sim = (sim_ms, now)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self.error:
                status = "failed"
            elif self.panic_count and self.process_running:
                status = "panic"
            elif not self.process_running:
                status = "stopped" if self.exit_code in (None, 0) else "failed"
            elif self.app_ready:
                status = "ready"
            elif self.app_main_entered:
                status = "app_main"
            elif self.rom_seen:
                status = "booting"
            else:
                status = "starting"

            speed_percent = None
            if self._first_sim and self._last_sim and self._last_sim[1] > self._first_sim[1]:
                sim_delta = self._last_sim[0] - self._first_sim[0]
                wall_delta_ms = (self._last_sim[1] - self._first_sim[1]) * 1000
                if sim_delta >= 0 and wall_delta_ms > 0:
                    speed_percent = round(sim_delta / wall_delta_ms * 100.0, 1)

            return {
                "type": "esp32_runtime",
                "target": "esp32s3",
                "status": status,
                "process_running": self.process_running,
                "exit_code": self.exit_code,
                "error": self.error,
                "rom_seen": self.rom_seen,
                "boot_count": self.boot_count,
                "reset_reason": dict(self.reset_reason) if self.reset_reason else None,
                "app_main_entered": self.app_main_entered,
                "gpio_configured": self.gpio_configured,
                "app_ready": self.app_ready,
                "panic_count": self.panic_count,
                "gpio_levels": dict(self.gpio_levels),
                "gpio_readback_levels": dict(self.gpio_readback_levels),
                "gpio_output_mismatch_count": self.gpio_output_mismatch_count,
                "gpio_output_mismatches": list(self._gpio_mismatches),
                "simulation_time_ms": self.sim_time_ms,
                "wall_elapsed_ms": round((time.monotonic() - self.started_at) * 1000, 3),
                "speed_percent": speed_percent,
                "uart_lines": list(self._lines),
                "events": list(self._events),
                "plot_series": {name: list(samples) for name, samples in self.plot_series.items()},
            }


class ESP32RuntimeSession:
    """Manage one ESP-IDF/QEMU monitor process and its UART observation stream."""

    def __init__(self):
        self._lock = threading.RLock()
        self.observer = ESP32RuntimeObserver()
        self._process: Any = None
        self._thread: threading.Thread | None = None
        self._project: Path | None = None
        self._backend_kind: str | None = None
        self._engine_kind: str | None = None
        self._stop_requested = False

    @staticmethod
    def _runtime_command(project: Path, env: Mapping[str, str]) -> tuple[list[str] | None, str | None]:
        idf_command, error = resolve_idf_command(env)
        if error or idf_command is None:
            return None, error or "无法找到 ESP-IDF 命令。"
        return [*idf_command, "-C", str(project), "qemu", "monitor"], None

    BACKENDS = {"auto", "qemu", "esp-emu"}
    ESP_EMU_VERSION = "0.51.0"

    @staticmethod
    def _find_esp_emu(
        env: Mapping[str, str] | None = None,
        *,
        repo_root: Path | None = None,
    ) -> Path | None:
        """Find esp-emu in an explicit override, PATH, or the repo-local tools directory."""
        current_env = os.environ if env is None else env
        candidates: list[Path] = []
        override = current_env.get("ZETSIM_ESP_EMU")
        if override:
            candidates.append(Path(override).expanduser())
        path_executable = shutil.which("esp-emu", path=current_env.get("PATH"))
        if path_executable:
            candidates.append(Path(path_executable))
        root = repo_root or Path(__file__).resolve().parents[1]
        tools_dir = root / ".tools" / f"esp-emu-{ESP32RuntimeSession.ESP_EMU_VERSION}"
        candidates.extend((tools_dir / "esp-emu", tools_dir / "esp-emu.exe"))
        for candidate in candidates:
            try:
                if candidate.is_file():
                    return candidate.resolve()
            except OSError:
                continue
        return None

    @staticmethod
    def _project_name(project: Path) -> str:
        """Read CMake's project() name because the directory and ELF names can differ."""
        source = (project / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(r"(?im)^\s*project\s*\(\s*([A-Za-z0-9_.+-]+)", source)
        if not match:
            raise ValueError(f"无法从 {project / 'CMakeLists.txt'} 读取 CMake project() 名称。")
        return match.group(1)

    @staticmethod
    def _run_idf_step(
        idf_command: list[str],
        project: Path,
        env: Mapping[str, str],
        args: list[str],
        timeout_s: int = 1200,
    ) -> tuple[bool, str]:
        command = [*idf_command, "-C", str(project), *args]
        try:
            result = subprocess.run(
                command,
                cwd=str(project),
                env=dict(env),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", "replace")
            return False, f"命令超时（{timeout_s}s）：{shlex.join(command)}\n{output[-6000:]}"
        except OSError as exc:
            return False, f"无法执行 {shlex.join(command)}：{exc}"
        output = result.stdout or ""
        if result.returncode:
            return False, f"命令失败（exit={result.returncode}）：{shlex.join(command)}\n{output[-8000:]}"
        return True, output

    @classmethod
    def _esp_emu_install_hint(cls, platform_name: str | None = None) -> str:
        version = cls.ESP_EMU_VERSION
        platform = os.name if platform_name is None else platform_name
        if platform == "nt":
            return (
                f"未找到 esp-emu（建议版本 {version}）。Espressif 当前安装说明提供 Linux x86_64/arm64 "
                "和 macOS Apple Silicon 原生二进制，没有列出 Windows 原生二进制。"
                "在 Windows 上请继续选择“Espressif QEMU”，或在 WSL2 Ubuntu 中安装/运行 zetsim，"
                "再在 WSL 的仓库根目录执行：\n"
                "curl -fsSL https://raw.githubusercontent.com/espressif/esp-emulator/v"
                f"{version}/install.sh | sh -s -- --version {version} --bin-dir "
                f".tools/esp-emu-{version} --force"
            )
        return (
            f"未找到 esp-emu（建议版本 {version}）。在仓库根目录运行以下命令安装到本地 .tools/ 目录：\n"
            "curl -fsSL https://raw.githubusercontent.com/espressif/esp-emulator/v"
            f"{version}/install.sh | sh -s -- --version {version} --bin-dir "
            f".tools/esp-emu-{version} --force"
        )

    def _prepare_esp_emu(
        self, project: Path, env: Mapping[str, str], emu: Path
    ) -> tuple[list[str] | None, str | None]:
        idf_command, error = resolve_idf_command(env)
        if error or idf_command is None:
            return None, error or "运行 esp-emu 需要可用的 ESP-IDF 环境。"
        try:
            project_name = self._project_name(project)
        except (OSError, ValueError) as exc:
            return None, str(exc)
        ok, output = self._run_idf_step(idf_command, project, env, ["build"])
        if not ok:
            return None, f"esp-emu 启动前编译失败：\n{output}"
        # ESP-IDF v6.1 runs merge-bin relative to build/, so output must be
        # "merged_flash.bin", not "build/merged_flash.bin".
        ok, output = self._run_idf_step(
            idf_command, project, env, ["merge-bin", "-o", "merged_flash.bin"]
        )
        if not ok:
            return None, f"esp-emu 启动前合并固件镜像失败：\n{output}"
        firmware = project / "build" / "merged_flash.bin"
        elf = project / "build" / f"{project_name}.elf"
        missing = [str(path) for path in (firmware, elf) if not path.is_file()]
        if missing:
            return None, "ESP-IDF 命令已完成，但缺少 esp-emu 运行文件：\n  " + "\n  ".join(missing)
        return [
            str(emu), "--chip", "esp32s3", "--firmware", str(firmware),
            "--elf", str(elf), "--console", "uart0",
        ], None

    def start(self, project_dir: str | Path, backend: str = "auto") -> tuple[bool, str | None]:
        with self._lock:
            if self._process is not None and self._is_alive(self._process):
                return False, "ESP32-S3 仿真已经在运行。"
            if not isinstance(backend, str) or backend not in self.BACKENDS:
                return False, f"仿真后端无效：{backend!r}；允许值：auto、esp-emu、qemu。"
            self._engine_kind = None
            try:
                project = validate_project(project_dir)
            except (OSError, ValueError) as exc:
                return False, str(exc)

            sdkconfig = project / "sdkconfig.defaults"
            if not sdkconfig.is_file() or 'CONFIG_IDF_TARGET="esp32s3"' not in sdkconfig.read_text(encoding="utf-8"):
                return False, "项目必须在 sdkconfig.defaults 中声明 CONFIG_IDF_TARGET=\"esp32s3\"。"

            env = dict(os.environ)
            env["IDF_TARGET"] = "esp32s3"
            emu = self._find_esp_emu(env)
            if backend == "esp-emu":
                if emu is None:
                    return False, self._esp_emu_install_hint()
                engine = "esp-emu"
            elif backend == "qemu":
                engine = "qemu"
            else:
                engine = "esp-emu" if emu is not None else "qemu"

            if engine == "esp-emu":
                if emu is None:
                    return False, self._esp_emu_install_hint()
                # This operation can build the project and merge a flash image;
                # callers should run it in a worker thread, not on the ASGI loop.
                command, error = self._prepare_esp_emu(project, env, emu)
                if error or command is None:
                    return False, error or "无法准备 esp-emu 固件。"
            else:
                command, error = self._runtime_command(project, env)
                if error or command is None:
                    return False, error or "无法初始化 ESP-IDF/QEMU 命令。"

            self.observer = ESP32RuntimeObserver()
            self._project = project
            self._stop_requested = False
            self._engine_kind = engine
            self._backend_kind = None
            try:
                if engine == "esp-emu":
                    proc = subprocess.Popen(
                        command,
                        cwd=str(project),
                        env=env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        bufsize=0,
                        start_new_session=(os.name != "nt"),
                    )
                    self._backend_kind = "esp-emu"
                elif os.name == "nt":
                    try:
                        from winpty import PtyProcess
                    except ImportError:
                        self._engine_kind = None
                        return False, (
                            "Windows 浏览器运行时需要安装可选伪终端依赖："
                            'python -m pip install -e ".[windows-pty]"'
                        )
                    command_line = subprocess.list2cmdline(command)
                    proc = PtyProcess.spawn(
                        command_line,
                        cwd=str(project),
                        env=env,
                        dimensions=(30, 120),
                        encoding="utf-8",
                    )
                    self._backend_kind = "winpty"
                else:
                    script = shutil.which("script", path=env.get("PATH"))
                    if not script:
                        self._engine_kind = None
                        return False, "未找到 util-linux 的 script；QEMU 串口捕获需要伪终端。"
                    proc = subprocess.Popen(
                        [script, "-q", "-f", "-e", "-c", shlex.join(command), "/dev/null"],
                        cwd=str(project),
                        env=env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        bufsize=0,
                        start_new_session=True,
                    )
                    self._backend_kind = "script"
            except (OSError, ValueError, TypeError) as exc:
                self._process = None
                self._backend_kind = None
                self._engine_kind = None
                return False, f"启动 ESP32-S3 / {engine} 仿真失败：{exc}"

            self._process = proc
            self.observer.set_process_state(True)
            self._thread = threading.Thread(
                target=self._reader_loop, args=(proc, self._backend_kind), daemon=True
            )
            self._thread.start()
            return True, None

    @staticmethod
    def _is_alive(process: Any) -> bool:
        if hasattr(process, "poll"):
            return process.poll() is None
        try:
            return bool(process.isalive())
        except Exception:
            return False

    def _reader_loop(self, process: Any, backend_kind: str | None) -> None:
        exit_code: int | None = None
        try:
            if backend_kind in {"script", "esp-emu"}:
                assert process.stdout is not None
                for raw in iter(process.stdout.readline, b""):
                    self.observer.ingest(raw)
                exit_code = int(process.wait())
            elif backend_kind == "winpty":
                while process.isalive():
                    line = process.readline()
                    if line:
                        self.observer.ingest(line)
                    else:
                        time.sleep(0.01)
                exit_code = getattr(process, "exitstatus", None)
        except Exception as exc:
            self.observer.set_process_state(False, error=f"读取 QEMU UART 输出失败：{exc}")
            return
        finally:
            self.observer.flush()
            with self._lock:
                stopped_by_user = self._stop_requested
                self.observer.set_process_state(
                    False,
                    exit_code=exit_code,
                    error=None if stopped_by_user or exit_code in (None, 0) else f"QEMU monitor 退出码：{exit_code}",
                )

    def send_serial(self, text: str) -> tuple[bool, str | None]:
        if not isinstance(text, str):
            return False, "串口输入必须是字符串。"
        if len(text) > 4096:
            return False, "单次串口输入不能超过 4096 个字符。"
        with self._lock:
            process, kind = self._process, self._backend_kind
            if process is None or not self._is_alive(process):
                return False, "ESP32-S3 仿真没有运行。"
            payload = text if text.endswith("\n") or text.endswith("\r") else text + "\r\n"
            try:
                if kind in {"script", "esp-emu"}:
                    if process.stdin is None:
                        return False, "仿真终端输入通道不可用。"
                    process.stdin.write(payload.encode("utf-8", "replace"))
                    process.stdin.flush()
                elif kind == "winpty":
                    process.write(payload)
                else:
                    return False, "未知的 QEMU 终端后端。"
            except (OSError, ValueError) as exc:
                return False, f"向 ESP32-S3 UART 发送数据失败：{exc}"
            return True, None

    @staticmethod
    def _descendant_pids_from_ps(root_pid: int, ps_output: str) -> list[int]:
        """Return descendants in parent-before-child order from a process table."""
        children: dict[int, list[int]] = {}
        for line in ps_output.splitlines():
            fields = line.split()
            if len(fields) != 2:
                continue
            try:
                pid, ppid = int(fields[0]), int(fields[1])
            except ValueError:
                continue
            children.setdefault(ppid, []).append(pid)
        ordered: list[int] = []
        queue = list(children.get(root_pid, []))
        while queue:
            pid = queue.pop(0)
            if pid == root_pid or pid in ordered:
                continue
            ordered.append(pid)
            queue.extend(children.get(pid, []))
        return ordered

    @classmethod
    def _signal_script_tree(cls, process: subprocess.Popen, sig: int) -> None:
        """Signal QEMU descendants as well as the PTY wrapper on POSIX hosts."""
        try:
            listing = subprocess.run(
                ["ps", "-eo", "pid=,ppid="],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            output = listing.stdout
            if listing.returncode != 0:
                fallback = subprocess.run(
                    ["ps", "-axo", "pid=,ppid="],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                output = fallback.stdout
            descendants = cls._descendant_pids_from_ps(process.pid, output)
        except (OSError, subprocess.TimeoutExpired):
            descendants = []
        for pid in reversed(descendants):
            try:
                os.kill(pid, sig)
            except (OSError, ProcessLookupError):
                pass
        try:
            os.kill(process.pid, sig)
        except (OSError, ProcessLookupError):
            pass

    def stop(self, timeout_s: float = 3.0) -> dict[str, Any]:
        with self._lock:
            process, kind = self._process, self._backend_kind
            if process is None or not self._is_alive(process):
                return self.snapshot()
            self._stop_requested = True
        try:
            if kind == "script":
                self._signal_script_tree(process, signal.SIGTERM)
                try:
                    process.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    self._signal_script_tree(process, signal.SIGKILL)
                    process.wait(timeout=1.0)
            elif kind == "esp-emu":
                process.terminate()
                try:
                    process.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
            elif kind == "winpty":
                try:
                    process.terminate(force=True)
                except TypeError:
                    process.terminate()
                deadline = time.monotonic() + timeout_s
                while process.isalive() and time.monotonic() < deadline:
                    time.sleep(0.05)
        except Exception as exc:
            self.observer.set_process_state(False, error=f"停止 ESP32-S3 仿真失败：{exc}")
        return self.snapshot()

    @classmethod
    def backend_availability(cls) -> dict[str, Any]:
        """Describe locally available backend prerequisites without starting them."""
        emu = cls._find_esp_emu()
        idf_command, idf_error = resolve_idf_command()
        if os.name == "nt":
            try:
                from winpty import PtyProcess  # noqa: F401
                qemu_console_ready = True
            except ImportError:
                qemu_console_ready = False
                qemu_console_error = 'Windows 交互式串口缺少 pywinpty；运行 python -m pip install -e ".[windows-pty]"'
            else:
                qemu_console_error = ""
        else:
            qemu_console_ready = shutil.which("script") is not None
            qemu_console_error = "" if qemu_console_ready else "未找到 util-linux 的 script 伪终端工具。"

        qemu_binary = any(shutil.which(name) for name in ("qemu-system-xtensa", "qemu-system-xtensa.exe"))
        qemu_available = bool(idf_command and qemu_binary and qemu_console_ready)
        qemu_reasons = []
        if idf_error:
            qemu_reasons.append(idf_error)
        if not qemu_binary:
            qemu_reasons.append("PATH 中未找到 qemu-system-xtensa；请激活 ESP-IDF 环境并安装 qemu-xtensa。")
        if not qemu_console_ready:
            qemu_reasons.append(qemu_console_error)
        return {
            "items": [
                {
                    "id": "auto",
                    "available": True,
                    "description": "存在 esp-emu 时优先使用；否则回退到 QEMU。",
                },
                {
                    "id": "esp-emu",
                    "available": emu is not None,
                    "version": cls.ESP_EMU_VERSION,
                    "executable": emu.name if emu else None,
                    "reason": "" if emu else cls._esp_emu_install_hint(),
                },
                {
                    "id": "qemu",
                    "available": qemu_available,
                    "reason": "" if qemu_available else " ".join(qemu_reasons),
                },
            ]
        }

    def snapshot(self) -> dict[str, Any]:
        state = self.observer.snapshot()
        state["backend"] = self._engine_kind or "none"
        return state
