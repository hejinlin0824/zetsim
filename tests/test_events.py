import json
from zetsim.events import EventBus

def test_event_bus_keeps_recent_events_and_notifies_subscribers():
    bus = EventBus()
    bus.max_log = 2
    received = []
    bus.subscribe("*", received.append)
    for i in range(3):
        bus.publish(i * 10, "gpio.PA5", i % 2)
    assert [event.t_ns for event in bus.log] == [10, 20]
    assert len(received) == 3
    assert bus.snapshot(since_ns=20)[0].t_ns == 20

def test_event_bus_exports_jsonl_and_vcd():
    bus = EventBus()
    bus.publish(100, "gpio.PA5", 1)
    bus.publish(150, "gpio.PA5", 0)
    bus.publish(160, "usart1.tx", b"OK")
    rows = [json.loads(line) for line in bus.to_jsonl().splitlines()]
    assert rows[2]["data"] == "OK"
    vcd = bus.to_vcd()
    assert "$timescale 1ns $end" in vcd
    assert "#100" in vcd and "#150" in vcd
    assert "1v0" in vcd and "0v0" in vcd
