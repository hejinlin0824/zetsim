"""zetsim CLI — 无头运行固件、查看 UART 输出、寄存器状态。"""
from __future__ import annotations
import argparse
import sys


def build_argparser():
    p = argparse.ArgumentParser(prog="zetsim", description="STM32F103ZET6 个人仿真器")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="运行固件")
    run.add_argument("firmware", help=".hex / .elf 文件")
    run.add_argument("--time", default="200ms", help="仿真时长，如 500ms / 2s")
    run.add_argument("--uart", type=int, default=1, help="回显哪个串口（默认 1）")
    run.add_argument("--cpi", type=float, default=2.0, help="每指令周期数（时间模型）")
    run.add_argument("--events", action="store_true", help="打印全部事件流")
    run.add_argument("--dump", action="store_true", help="结束时打印寄存器 dump")
    run.add_argument("--trace-gpio", action="store_true", help="打印 GPIO 事件")

    serve = sub.add_parser("serve", help="启动 Web 仪表盘")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--firmware", default=None, help="启动即加载的固件")
    return p


def parse_time(s: str) -> float:
    s = s.strip().lower()
    if s.endswith("ms"):
        return float(s[:-2])
    if s.endswith("s"):
        return float(s[:-1]) * 1000
    return float(s)


def cmd_run(args):
    from .board import Board
    from .engine import Simulation
    from rich.console import Console
    from rich.table import Table

    console = Console()
    board = Board(cpi=args.cpi)
    board.reset()
    try:
        board.core.load_file(args.firmware)
    except Exception as e:
        console.print(f"[red]固件加载失败: {e}[/red]")
        return 2

    uart_topic = f"usart{args.uart}.tx"
    text = bytearray()
    if args.events:
        board.events.subscribe("*", lambda e: print(f"[{e.t_ns/1e6:10.3f}ms] {e.topic} {e.data}"))
    elif not args.trace_gpio:
        board.events.subscribe(uart_topic, lambda e: text.append(e.data))
    if args.trace_gpio:
        board.events.subscribe("gpio.*", lambda e: print(f"[{e.t_ns/1e6:10.3f}ms] {e.topic} = {e.data}"))

    sim = Simulation(board)
    report = sim.run(until_ms=parse_time(args.time))

    console.print(f"[bold]仿真结束[/bold]: {report.halt_reason}  "
                  f"t={report.time_ns/1e6:.3f}ms  指令={report.instructions:,}  异常进入={report.exceptions}")
    if text:
        console.print(f"[green]UART{args.uart} 输出 ({len(text)} 字节):[/green]")
        console.print(bytes(text).decode("utf-8", "replace"))
    if report.error:
        console.print(f"[red]错误: {report.error}[/red]")
    if args.dump:
        t = Table(title="CPU 状态")
        t.add_column("reg"); t.add_column("value", justify="right")
        for k, v in report.dump["regs"].items():
            t.add_row(k, f"{v:#010x}" if isinstance(v, int) else str(v))
        console.print(t)
    return 0


def cmd_serve(args):
    from .webapp import serve
    serve(host=args.host, port=args.port, firmware=args.firmware)
    return 0


def main(argv=None):
    args = build_argparser().parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "serve":
        return cmd_serve(args)


if __name__ == "__main__":
    sys.exit(main())
