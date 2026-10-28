#!/usr/bin/env bash
# CI smoke test: build a real ESP-IDF app and boot it in Espressif QEMU.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root/projects/esp32s3_blink"

python "$IDF_PATH/tools/idf_tools.py" --non-interactive install qemu-xtensa
# Install adds the binary but PATH is refreshed by export.sh.
. "$IDF_PATH/export.sh" >/dev/null

idf.py build

log_file="$(mktemp)"
if ! command -v script >/dev/null 2>&1; then
    echo "The QEMU smoke test requires the util-linux script command for a pseudo-terminal." >&2
    exit 2
fi
# QEMU's stdio serial backend needs a TTY; script provides a PTY while recording UART output.
# Stop the QEMU child directly. Wrapping idf.py in timeout can kill only the
# parent while leaving the QEMU subprocess attached to the PTY indefinitely.
script -q -c "idf.py qemu" "$log_file" &
session_pid=$!

# Let the app boot and emit multiple UART heartbeats before stopping QEMU.
sleep 15
pkill -TERM -f '[q]emu-system-xtensa -M esp32s3' || true
sleep 2
pkill -KILL -f '[q]emu-system-xtensa -M esp32s3' || true
pkill -TERM -f '[i]df.py qemu' || true
sleep 1
kill -TERM "$session_pid" 2>/dev/null || true
wait "$session_pid" 2>/dev/null || true
cat "$log_file"

grep -Fq "ZETSIM_ESP32S3_BOOT_OK" "$log_file"
grep -Fq "ZETSIM_ESP32S3_GPIO2=" "$log_file"
rm -f "$log_file"
echo "ESP32-S3 QEMU boot and UART heartbeat verified."
