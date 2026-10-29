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
cleanup() {
    rm -f "$log_file"
}
trap cleanup EXIT

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

# A panic is a failed smoke test even if a later reboot accidentally prints a
# marker. Symbolize the Xtensa PC/backtrace against the exact ELF from this run.
if grep -Fq "Guru Meditation Error" "$log_file"; then
    echo "ESP32-S3 QEMU panic detected; attempting Xtensa backtrace symbolization." >&2
    elf="$PWD/build/zetsim_esp32s3_blink.elf"
    addr2line="$(command -v xtensa-esp32s3-elf-addr2line || true)"
    if [[ -n "$addr2line" && -f "$elf" ]]; then
        pc="$(sed -nE 's/.*PC[[:space:]]*:[[:space:]]*(0x[0-9a-fA-F]+).*/\1/p' "$log_file" | head -n 1)"
        backtrace="$(sed -nE 's/.*Backtrace:[[:space:]]*(.*)/\1/p' "$log_file" | head -n 1)"
        addresses=()
        [[ -n "$pc" ]] && addresses+=("$pc")
        if [[ -n "$backtrace" ]]; then
            while IFS= read -r address; do
                addresses+=("$address")
            done < <(printf '%s\n' "$backtrace" | grep -oE '0x[0-9a-fA-F]{8}' || true)
        fi
        if (( ${#addresses[@]} )); then
            echo "Decoded panic frames (ELF: $elf):" >&2
            "$addr2line" -pfiaC -e "$elf" "${addresses[@]}" || true
        else
            echo "Panic found, but no PC/backtrace addresses could be parsed." >&2
        fi
    else
        echo "xtensa-esp32s3-elf-addr2line or the built ELF is missing; raw panic is above." >&2
    fi
    exit 1
fi

grep -Fq "ESP-ROM:esp32s3" "$log_file"
grep -Eq 'rst:0x1 \(POWERON(_RESET)?\)' "$log_file"
grep -Fq "ZETSIM_ESP32S3_APP_MAIN_ENTERED" "$log_file"
grep -Fq "ZETSIM_ESP32S3_GPIO_CONFIG_OK" "$log_file"
grep -Fq "ZETSIM_ESP32S3_BOOT_OK" "$log_file"
grep -Fq "ZETSIM_ESP32S3_GPIO2=" "$log_file"
echo "ESP32-S3 QEMU boot, app_main, GPIO setup, and UART heartbeat verified."
