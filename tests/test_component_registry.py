from zetsim.component_registry import COMPONENTS, component_catalog, component_pin_defs, get_component

def test_registry_preserves_existing_schematic_pin_contract():
    pins = component_pin_defs()
    assert pins["mcu"][-2:] == ["VDD", "VSS"]
    assert pins["led"] == ["A", "K"]
    assert pins["resistor"] == ["1", "2"]
    assert "avr" not in COMPONENTS and "rp2040" not in COMPONENTS

def test_catalog_is_defensive_and_exposes_model_capabilities():
    led = next(item for item in component_catalog() if item["type"] == "led")
    assert {"digital", "analog"} <= set(led["capabilities"])
    led["pins"].append("MUTATED")
    assert "MUTATED" not in get_component("led")["pins"]
