#!/usr/bin/env python3
"""End-to-end UART1 loopback test for an ESP32-S3 image under esp-emu."""
from __future__ import annotations
import argparse
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

READY_MARKER = "ZETSIM_UART1_ECHO_READY"
RX_MARKER = "ZETSIM_UART1_ECHO_RX_BYTES="
PAYLOAD = b"ZETSIM_UART1_PING_5A7B9C\r\n"


class LogCapture:
    def __init__(self, destination: Path):
        self.destination = destination
        self.lines: list[str] = []
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.rx_logged = threading.Event()

    def reader(self, pipe) -> None:
        with self.destination.open("w", encoding="utf-8", errors="replace") as log:
            for line in iter(pipe.readline, ""):
                with self.lock:
                    self.lines.append(line)
                log.write(line)
                log.flush()
                if READY_MARKER in line:
                    self.ready.set()
                if RX_MARKER in line:
                    self.rx_logged.set()

    def snapshot(self) -> str:
        with self.lock:
            return "".join(self.lines)


def _unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_connection(port: int, timeout_s: float) -> socket.socket:
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            sock.settimeout(0.5)
            return sock
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    raise TimeoutError(f"UART1 TCP bridge did not accept a client on 127.0.0.1:{port}: {last_error}")


def _read_until(sock: socket.socket, expected: bytes, timeout_s: float) -> bytes:
    deadline = time.monotonic() + timeout_s
    result = bytearray()
    while time.monotonic() < deadline and expected not in result:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            break
        result.extend(chunk)
    return bytes(result)


def run_uart1_smoke(emu: Path, firmware: Path, elf: Path, log_path: Path) -> None:
    for path in (emu, firmware, elf):
        if not path.is_file():
            raise FileNotFoundError(f"Required UART1 smoke input does not exist: {path}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    port = _unused_local_port()
    command = [
        str(emu), "--chip", "esp32s3", "--firmware", str(firmware), "--elf", str(elf),
        "--console", "uart0", "--uart1-tcp", f"127.0.0.1:{port}", "--timeout", "15s",
    ]
    print("$ " + " ".join(command), flush=True)
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    assert process.stdout is not None
    capture = LogCapture(log_path)
    reader = threading.Thread(target=capture.reader, args=(process.stdout,), daemon=True)
    reader.start()
    client: socket.socket | None = None
    try:
        if not capture.ready.wait(timeout=9.0):
            raise TimeoutError(f"UART1 firmware did not become ready.\n{capture.snapshot()}")
        client = _wait_for_connection(port, timeout_s=4.0)
        client.sendall(PAYLOAD)
        received = _read_until(client, PAYLOAD, timeout_s=4.0)
        if PAYLOAD not in received:
            raise RuntimeError(f"UART1 echo mismatch. expected={PAYLOAD!r}, received={received!r}\n{capture.snapshot()}")
        if not capture.rx_logged.wait(timeout=2.0):
            raise TimeoutError("TCP echo arrived but UART0 did not report RX bytes.\n" + capture.snapshot())
        log = capture.snapshot()
        if "ZETSIM_UART1_ECHO_WRITE_MISMATCH" in log:
            raise RuntimeError("ESP-IDF UART1 reported a short TX write.\n" + log)
        print(f"UART1 echo bytes verified: {len(PAYLOAD)} bytes on TCP port {port}.", flush=True)
        print("UART1 RX driver marker verified on the UART0 console.", flush=True)
    finally:
        if client is not None:
            client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
        reader.join(timeout=2.0)
        if process.stdout:
            process.stdout.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emu", type=Path, required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_uart1_smoke(args.emu.resolve(), args.firmware.resolve(), args.elf.resolve(), args.log.resolve())
    except (OSError, RuntimeError, TimeoutError) as exc:
        print(f"UART1 smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
