"""Regression tests for creating and protecting HAL-based C project templates."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from zetsim import build
from zetsim.webapp import build_app


def _write_template(root: Path) -> Path:
    template = root / "projects" / "led_marquee"
    template.mkdir(parents=True)
    (template / "main.c").write_text(
        '#include "stm32f1xx_hal.h"\nint main(void) { HAL_Init(); for (;;) {} }\n',
        encoding="utf-8",
    )
    (template / "startup.c").write_text("void Reset_Handler(void) {}\n", encoding="utf-8")
    (template / "stm32f1xx_hal_conf.h").write_text(
        "#ifndef STM32F1XX_HAL_CONF_H\n#define STM32F1XX_HAL_CONF_H\n"
        "#define HAL_MODULE_ENABLED\n#endif\n",
        encoding="utf-8",
    )
    (template / "link.ld").write_text("/* test linker script */\n", encoding="utf-8")
    return template


def test_project_template_tracks_hal_config_as_a_required_file() -> None:
    assert build.PROJECT_FILES == (
        "main.c",
        "startup.c",
        "stm32f1xx_hal_conf.h",
        "link.ld",
    )
    assert "stm32f1xx_hal_conf.h" in build.PROTECTED
    assert "stm32f103.h" not in build.PROJECT_FILES


def test_creating_a_project_copies_hal_config_and_prevents_its_deletion(
    tmp_path: Path, monkeypatch
) -> None:
    _write_template(tmp_path)
    monkeypatch.chdir(tmp_path)

    with TestClient(build_app()) as client:
        created = client.post("/api/projects", json={"name": "my_hal_project"})
        assert created.status_code == 200, created.text
        assert created.json()["ok"] is True

        project_dir = tmp_path / "projects" / "my_hal_project"
        for filename in build.PROJECT_FILES:
            assert (project_dir / filename).is_file(), f"template omitted {filename}"

        loaded = client.get("/api/project/my_hal_project")
        assert loaded.status_code == 200, loaded.text
        assert "stm32f1xx_hal_conf.h" in loaded.json()["files"]

        deleted = client.delete(
            "/api/project/my_hal_project/file/stm32f1xx_hal_conf.h"
        )
        assert deleted.status_code == 400
        assert (project_dir / "stm32f1xx_hal_conf.h").is_file()
