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
set +e
timeout --kill-after=5s 12s idf.py qemu >"$log_file" 2>&1
qemu_status=$?
set -e
cat "$log_file"

# QEMU intentionally runs forever because the example blinks continuously.
# GNU timeout commonly returns 124; 143 can be returned when TERM reaches QEMU.
if [ "$qemu_status" -ne 0 ] && [ "$qemu_status" -ne 124 ] && [ "$qemu_status" -ne 143 ]; then
    rm -f "$log_file"
    exit "$qemu_status"
fi

grep -Fq "ZETSIM_ESP32S3_BOOT_OK" "$log_file"
grep -Fq "ZETSIM_ESP32S3_GPIO2=" "$log_file"
rm -f "$log_file"
echo "ESP32-S3 QEMU boot and UART heartbeat verified."
