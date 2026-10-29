from __future__ import annotations
import pytest
from zetsim.board_rules import check_board_wiring
from zetsim.boards import get_board

@pytest.fixture
def board():
    return get_board("esp32-s3-devkitc-1")

def codes(report):
    return {item["code"] for item in report["findings"]}

def test_strap_pin_external_drive_during_reset_is_an_error_and_warns_about_boot(board):
    report=check_board_wiring(board,{"assignments":[{"pin":"0","mode":"gpio_input","during_reset":True,"external_level":"high"}]})
    assert report["ok"] is False
    assert {"STRAP_PIN_ASSIGNED","STRAP_RESET_DRIVE"} <= codes(report)

def test_uart_usb_jtag_and_flash_psram_repurposing_are_warned(board):
    report=check_board_wiring(board,{"assignments":[{"pin":"TX","mode":"gpio_output"},{"pin":"19","mode":"gpio_input"},{"pin":"39","mode":"gpio_output"},{"pin":"35","mode":"gpio_input"}]})
    assert report["ok"] is True
    assert {"UART0_TX_REPURPOSED","USB_SERIAL_JTAG_CONFLICT","JTAG_PIN_REPURPOSED","FLASH_PSRAM_PIN_CHECK"} <= codes(report)

def test_same_physical_pin_cannot_be_assigned_twice(board):
    report=check_board_wiring(board,{"assignments":[{"pin":"TX","mode":"uart_tx"},{"pin":"TX","mode":"gpio_output"}]})
    assert report["ok"] is False
    assert "GPIO_ASSIGNED_MULTIPLE_TIMES" in codes(report)

@pytest.mark.parametrize("entry",[
 {"pin":"MISSING","mode":"gpio_input"},{"pin":"5V","mode":"gpio_output"},
 {"pin":"0","mode":"unsafe"},{"pin":"1","mode":"gpio_output","during_reset":"yes"},
 {"pin":"1","mode":"gpio_output","external_level":"maybe"}
])
def test_invalid_board_wiring_inputs_are_rejected(board,entry):
    with pytest.raises(ValueError): check_board_wiring(board,{"assignments":[entry]})

def test_empty_or_clean_board_wiring_plan_has_explanatory_result(board):
    assert "NO_ASSIGNMENTS" in codes(check_board_wiring(board,{"assignments":[]}))
    clean=check_board_wiring(board,{"assignments":[{"pin":"2","mode":"gpio_output"}]})
    assert clean["ok"] is True and "BOARD_WIRING_CLEAN" in codes(clean)
