"""事件总线：引擎与前端/器件解耦的唯一通道。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Event:
    t_ns: int          # 仿真时间戳（纳秒）
    topic: str         # 如 "usart1.tx" / "gpio.PA5" / "led1" / "sim.halt"
    data: object       # 任意负载


class EventBus:
    def __init__(self):
        self._subs: dict[str, list[Callable]] = {}
        self.log: list[Event] = []          # 全量录制（Recorder 的地基）
        self.max_log = 200_000

    def subscribe(self, topic: str, fn: Callable):
        self._subs.setdefault(topic, []).append(fn)

    def publish(self, t_ns: int, topic: str, data=None):
        if len(self.log) < self.max_log:
            self.log.append(Event(t_ns, topic, data))
        for fn in self._subs.get(topic, ()):
            fn(Event(t_ns, topic, data))
        for fn in self._subs.get("*", ()):
            fn(Event(t_ns, topic, data))

    def query(self, topic: str) -> list[Event]:
        return [e for e in self.log if e.topic == topic]

    def clear(self):
        self.log.clear()
