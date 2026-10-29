"""Static board-wiring checks driven by board metadata; not an electrical simulator."""
from __future__ import annotations
from typing import Any
from .boards import BoardDefinition, get_board

MODES={"gpio_input","gpio_output","uart_tx","uart_rx","i2c_sda","i2c_scl","spi_sck","spi_mosi","spi_miso","pwm","adc","usb_serial_jtag","jtag"}
LEVELS={"undriven","low","high"}

def check_board_wiring(board: BoardDefinition, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload,dict): raise ValueError("接线检查请求必须是 JSON 对象")
    assignments=payload.get("assignments",[])
    if not isinstance(assignments,list): raise ValueError("assignments 必须是数组")
    if len(assignments)>128: raise ValueError("单次接线检查最多支持 128 条引脚分配")
    findings=[]; normalized=[]; used={}
    def add(severity,code,title,detail,pin="",gpio=""):
        findings.append({"severity":severity,"code":code,"title":title,"detail":detail,"pin":pin,"gpio":gpio})
    for i,raw in enumerate(assignments):
        label=f"第 {i+1} 项"
        if not isinstance(raw,dict): raise ValueError(f"{label}必须是对象")
        pin_name,mode,name=raw.get("pin"),raw.get("mode"),raw.get("name","")
        reset,level=raw.get("during_reset",False),raw.get("external_level","undriven")
        if not isinstance(pin_name,str) or not pin_name: raise ValueError(f"{label}的 pin 必须是非空字符串")
        if not isinstance(mode,str) or mode not in MODES: raise ValueError(f"{label}的 mode 无效")
        if not isinstance(name,str) or len(name)>80: raise ValueError(f"{label}的 name 必须是 80 字符以内的字符串")
        if not isinstance(reset,bool): raise ValueError(f"{label}的 during_reset 必须是布尔值")
        if not isinstance(level,str) or level not in LEVELS: raise ValueError(f"{label}的 external_level 必须是 undriven、low 或 high")
        pin=board.pins.get(pin_name)
        if pin is None:
            add("error","PIN_UNKNOWN","针脚别名不存在",f"板卡 {board.name} 没有名为 {pin_name} 的针脚别名。",pin_name); continue
        if pin.kind!="gpio" or pin.gpio is None:
            add("error","PIN_NOT_GPIO","所选针脚不能作为 GPIO 使用",f"{pin_name} 映射到 {pin.target}（类型 {pin.kind}），不能按普通 GPIO 信号配置。",pin_name); continue
        item={"pin":pin_name,"gpio":pin.gpio,"mode":mode,"name":name,"during_reset":reset,"external_level":level,"constraints":list(pin.constraints)}
        normalized.append(item); used.setdefault(pin.gpio,[]).append(item)
        constraints=set(pin.constraints)
        if "strapping" in constraints or "boot-mode" in constraints:
            add("warn","STRAP_PIN_ASSIGNED","使用了启动配置相关 GPIO",f"{pin_name}（GPIO{pin.gpio}）参与启动绑带配置。确认外部电路在复位采样时不会把引脚拉到不符合目标启动配置的电平。",pin_name,f"GPIO{pin.gpio}")
            if reset and level in {"low","high"}:
                add("error","STRAP_RESET_DRIVE","复位期间有外部电平驱动启动配置引脚",f"{pin_name}（GPIO{pin.gpio}）被声明为复位期间由外部驱动为 {level.upper()}；这可能改变启动模式或电源配置。",pin_name,f"GPIO{pin.gpio}")
        if mode=="gpio_output" and reset and level in {"low","high"}:
            add("warn","OUTPUT_RESET_EXTERNAL_DRIVE","输出脚在复位期间被外部电路驱动",f"{pin_name}（GPIO{pin.gpio}）计划作为 GPIO 输出，但外部电平在复位期间为 {level.upper()}。检查时序和驱动冲突。",pin_name,f"GPIO{pin.gpio}")
        rules=[
          ("uart0-default-tx",mode!="uart_tx","UART0_TX_REPURPOSED","UART0 默认发送脚被改作其他用途",f"{pin_name}（GPIO{pin.gpio}）是板卡映射中的 UART0 默认 TX；改作 {mode} 可能影响启动日志或串口监视器。"),
          ("uart0-default-rx",mode!="uart_rx","UART0_RX_REPURPOSED","UART0 默认接收脚被改作其他用途",f"{pin_name}（GPIO{pin.gpio}）是板卡映射中的 UART0 默认 RX；改作 {mode} 可能影响串口输入。"),
          ("usb-serial-jtag",mode!="usb_serial_jtag","USB_SERIAL_JTAG_CONFLICT","引脚可能与 USB Serial/JTAG 冲突",f"{pin_name}（GPIO{pin.gpio}）与 USB Serial/JTAG 共用相关信号；确认接口后再用于 {mode}。"),
          ("jtag",mode!="jtag","JTAG_PIN_REPURPOSED","JTAG 相关引脚被改作其他用途",f"{pin_name}（GPIO{pin.gpio}）可能与 JTAG 调试信号冲突；如需外部调试，请保留这些引脚。")
        ]
        for constraint,condition,code,title,detail in rules:
            if constraint in constraints and condition: add("warn",code,title,detail,pin_name,f"GPIO{pin.gpio}")
        if any("flash-psram" in c or "octal-flash" in c for c in constraints):
            add("warn","FLASH_PSRAM_PIN_CHECK","需要核对 Flash/PSRAM 引脚占用",f"{pin_name}（GPIO{pin.gpio}）可能受模组、Flash/PSRAM 类型或容量配置影响；请核对具体模组资料。",pin_name,f"GPIO{pin.gpio}")
    for gpio,group in sorted(used.items()):
        if len(group)>1:
            aliases=", ".join(x["pin"] for x in group)
            add("error","GPIO_ASSIGNED_MULTIPLE_TIMES","同一个 GPIO 被重复分配",f"{aliases} 都映射到 GPIO{gpio}。每个物理 GPIO 应有一个明确用途。",aliases,f"GPIO{gpio}")
    if not assignments: add("info","NO_ASSIGNMENTS","尚无待检查的接线","先将板卡针脚加入接线清单，再运行检查。")
    if not findings: add("info","BOARD_WIRING_CLEAN","未发现已知板级约束冲突","当前清单未触发已登记规则；这不替代电气兼容性和真实硬件验证。")
    errors=sum(x["severity"]=="error" for x in findings); warnings=sum(x["severity"]=="warn" for x in findings); infos=sum(x["severity"]=="info" for x in findings)
    return {"board_id":board.id,"board_name":board.name,"ok":True,"valid":errors==0,"summary":{"errors":errors,"warnings":warnings,"infos":infos},"assignments":normalized,"findings":findings,"scope_note":"板级静态规则检查；不模拟电气网络，不替代 ESP32-S3 QEMU 或真实硬件验证。"}

def check_board_id(board_id: str, payload: dict[str,Any]) -> dict[str,Any]:
    return check_board_wiring(get_board(board_id),payload)
