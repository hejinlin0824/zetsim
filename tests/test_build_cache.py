from zetsim import build_cache

def test_build_cache_key_changes_when_header_changes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.c").write_text("int main(void) { return 0; }", encoding="utf-8")
    header = project / "board.h"
    header.write_text("#define VALUE 1", encoding="utf-8")
    monkeypatch.setattr(build_cache, "_REPO", tmp_path / "repo")
    monkeypatch.setattr(build_cache.subprocess, "run",
        lambda *args, **kwargs: __import__("subprocess").CompletedProcess(args[0], 0, "gcc version 1", ""))
    first = build_cache.build_cache_key(project, "fake-gcc", hal_project=False, flags=["-O0"])
    header.write_text("#define VALUE 2", encoding="utf-8")
    second = build_cache.build_cache_key(project, "fake-gcc", hal_project=False, flags=["-O0"])
    assert first != second

def test_cache_restore_requires_both_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(build_cache, "_CACHE_ROOT", tmp_path / "cache")
    project = tmp_path / "project"
    project.mkdir()
    entry = tmp_path / "cache" / "abc"
    entry.mkdir(parents=True)
    (entry / "firmware.hex").write_text(":00000001FF\n", encoding="utf-8")
    assert not build_cache.restore_cached_build(project, "abc")
    (entry / "firmware.elf").write_bytes(b"ELF")
    assert build_cache.restore_cached_build(project, "abc")
    assert (project / "firmware.hex").exists() and (project / "firmware.elf").exists()
