# ESP32-S3 支持与边界

## 为什么使用独立后端？

ESP32-S3 使用双核 Xtensa LX7，而当前 zetsim 的原生模拟器基于 Unicorn ARM Cortex-M3；两者的指令集、启动流程、内存映射及外设寄存器均不同。因此，不能把 ESP32-S3 ELF/BIN 直接传给现有 STM32 `run` 或 `build` 命令。

zetsim 当前通过乐鑫官方工具链调用 ESP-IDF 构建系统，并使用 Espressif 维护的 QEMU 分支执行 ESP32-S3 固件。这比自己编造 Xtensa 指令执行层更可靠，也能运行真正的 ESP-IDF 应用。

官方资料：
- ESP32-S3 芯片和架构：https://www.espressif.com/products/socs/esp32-s3
- ESP-IDF ESP32-S3 文档：https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/
- Espressif QEMU 用法：https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/tools/qemu.html
- Espressif QEMU 支持矩阵：https://github.com/espressif/esp-toolchain-docs/blob/main/qemu/README.md

## 快速开始

工程：`projects/esp32s3_blink`

```powershell
python -m zetsim esp32 build projects/esp32s3_blink
python -m zetsim esp32 run projects/esp32s3_blink
```

`run` 对应官方 `idf.py qemu monitor`。可使用 `--graphics` 请求 QEMU 虚拟 framebuffer，但该 framebuffer 不是 ESP32-S3 的真实硬件；普通 GPIO 闪灯示例只通过 UART 打印输出，因此默认不需要图形窗口。

Windows 上应先打开 ESP-IDF PowerShell，或在当前 PowerShell 中载入安装好的 ESP-IDF 环境。Linux/macOS 需要 source 对应的 `export.sh`。首次准备 QEMU 时执行：

```powershell
python "$env:IDF_PATH/tools/idf_tools.py" install qemu-xtensa
```

## 当前覆盖范围

| 能力 | 当前状态 |
|---|---|
| ESP-IDF 项目构建 | 支持，通过 `idf.py build` |
| Xtensa LX7 CPU / ESP32-S3 启动 | 交由 Espressif QEMU，非 zetsim 的 Unicorn 内核 |
| UART 控制台 | 支持，通过 IDF monitor |
| 示例 GPIO 配置/输出 | 由官方 QEMU SoC 模型处理；例程有心跳输出 |
| STM32 原理图画布、既有 STM32 器件和 mini-SPICE 联动 | 暂不支持 ESP32-S3 直连 |
| 完整芯片外设、Wi-Fi/蓝牙射频、逐周期/电气级精度 | 不承诺；以 QEMU 官方支持矩阵为准 |

这一步完成的是能构建并启动真正 ESP-IDF 固件的基础接入，不会把 QEMU 未实现的硬件行为描述为已经仿真。
