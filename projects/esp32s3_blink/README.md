# ESP32-S3 GPIO 闪灯（ESP-IDF + Espressif QEMU）

本例使用乐鑫官方 ESP-IDF 的 `gpio_config()`、`gpio_set_level()` 与 FreeRTOS 延时，在 ESP32-S3 上运行。ESP32-S3 是 Xtensa LX7 芯片，不能用 `python -m zetsim build` 的 STM32/Cortex-M3 编译器路径。

## 准备环境

先安装 Espressif ESP-IDF（CI 固定使用 v6.1）。Windows 请打开安装器提供的 **ESP-IDF PowerShell**；Linux/macOS 请在当前终端加载 ESP-IDF 的 `export.sh`。确认当前环境能运行 `idf.py --version`。

安装 Espressif QEMU 的 Xtensa 版本：

```powershell
python "$env:IDF_PATH/tools/idf_tools.py" install qemu-xtensa
. "$env:IDF_PATH/export.ps1"
```

如果 PowerShell 的执行策略或当前 ESP-IDF 安装方式不支持上述第二条命令，请重新打开 ESP-IDF PowerShell。Linux/macOS 对应命令为：

```bash
python "$IDF_PATH/tools/idf_tools.py" install qemu-xtensa
. "$IDF_PATH/export.sh"
```

## 构建与运行

在仓库根目录执行：

```powershell
python -m zetsim esp32 build projects/esp32s3_blink
python -m zetsim esp32 run projects/esp32s3_blink
```

运行命令会由 `idf.py qemu monitor` 构建（如果需要）并启动 Espressif QEMU，在终端显示模拟 UART 输出。成功启动后应出现 `ZETSIM_ESP32S3_BOOT_OK` 和周期性 `ZETSIM_ESP32S3_GPIO2=0/1` 日志。按 ESP-IDF monitor 的提示退出。

## 支持范围

当前集成的是**独立的 ESP32-S3 执行后端**，调用真实 ESP-IDF 工程和 Espressif QEMU。它不使用 STM32 的 Unicorn 内核，也尚未把 ESP32-S3 引脚、电源、GPIO 波形及其所有外设接入 zetsim 现有的 STM32 原理图画布。QEMU 对 ESP32-S3 的外设覆盖是一个可验证子集，不等于完整逐周期电气仿真。CI 自动构建该工程，并启动 QEMU 验证应用能启动及输出心跳。
