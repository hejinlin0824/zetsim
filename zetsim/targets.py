"""Supported MCU target metadata; intentionally limited to STM32F103ZET6 and ESP32-S3."""
TARGETS = {
    "stm32f103zet6": {"label": "STM32F103ZET6", "architecture": "arm-cortex-m3", "backend": "unicorn", "build_system": "arm-none-eabi-gcc", "status": "primary"},
    "esp32s3": {"label": "ESP32-S3", "architecture": "xtensa-lx7", "backend": "espressif-qemu", "build_system": "esp-idf", "status": "secondary"},
}

def get_target(target_id: str) -> dict:
    try:
        return dict(TARGETS[target_id.lower()])
    except (KeyError, AttributeError) as exc:
        raise ValueError(f"不支持的目标 {target_id!r}；当前仅支持：{', '.join(TARGETS)}") from exc
