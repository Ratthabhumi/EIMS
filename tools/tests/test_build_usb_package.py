"""Deterministic, offline unit tests for the portable USB Auditor builder."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_usb_package as b  # noqa: E402

REPO_ROOT = b.REPO_ROOT


def _write(path: Path, content: str | bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))


def _make_valid_package(tmp_path: Path) -> Path:
    pkg = tmp_path / "EIMS_USB_Auditor"
    for rel in b.REQUIRED_PACKAGE_FILES:
        _write(pkg / rel)
    _write(pkg / "runtime/python/python314._pth")
    (pkg / "VERSION.txt").write_text(b.version_text(REPO_ROOT), encoding="utf-8")
    b.write_manifest(pkg)
    return pkg


def test_all_allowlist_sources_exist() -> None:
    missing = [rel for rel in b.SOURCE_ALLOWLIST if not (b.SOURCE_ROOT / rel).is_file()]
    assert missing == []


def test_allowlist_excludes_dev_and_generated_parts() -> None:
    forbidden_parts = {"tests", ".venv", "reports", "logs", "__pycache__"}
    for rel in b.SOURCE_ALLOWLIST:
        parts = set(Path(rel).parts)
        assert not (parts & forbidden_parts), rel
        assert not rel.endswith(".pyc"), rel
        assert rel != "Summary.xlsx"


def test_forbidden_markers_do_not_flag_shipped_paths() -> None:
    shipped = list(b.SOURCE_ALLOWLIST) + [
        "Run-EIMS-Audit.bat",
        "VERSION.txt",
        "runtime/python/python.exe",
        "runtime/python/python314._pth",
        "runtime/python/python314.zip",
        "runtime/python/Lib/site-packages/psutil/__init__.py",
        "runtime/python/Lib/site-packages/openpyxl/__init__.py",
    ]
    for rel in shipped:
        lowered = rel.lower()
        for marker in b.FORBIDDEN_PATH_MARKERS:
            assert marker not in lowered, f"{marker!r} matched {rel!r}"


def test_forbidden_markers_do_not_flag_dependency_internals() -> None:
    runtime_paths = [
        "runtime/python/Lib/site-packages/openpyxl/formula/tokenizer.py",
        "runtime/python/Lib/site-packages/openpyxl/worksheet/_writer.py",
        "runtime/python/Lib/site-packages/et_xmlfile/__init__.py",
        "runtime/python/Lib/site-packages/psutil/_psutil_windows.pyd",
        "runtime/python/Lib/site-packages/psutil/__init__.py",
    ]
    for rel in runtime_paths:
        lowered = rel.lower()
        for marker in b.FORBIDDEN_PATH_MARKERS:
            assert marker not in lowered, f"{marker!r} matched {rel!r}"


def test_manifest_round_trip(tmp_path: Path) -> None:
    pkg = tmp_path / "P"
    _write(pkg / "a.py", b"abc")
    _write(pkg / "b/c.py", b"hello world")
    _write(pkg / "b/d.txt", "data".encode("utf-8"))
    b.write_manifest(pkg)
    records = b.parse_manifest(pkg / "MANIFEST.txt")
    assert set(records) == {"a.py", "b/c.py", "b/d.txt"}
    assert records["a.py"] == (3, b._sha256_hex(pkg / "a.py"))
    assert records["b/c.py"] == (11, b._sha256_hex(pkg / "b/c.py"))


def test_check_package_ok_on_valid_synthetic_package(tmp_path: Path) -> None:
    pkg = _make_valid_package(tmp_path)
    assert b.build_manifest(pkg)
    assert b.find_problems(pkg) == []


def test_check_detects_tampered_file(tmp_path: Path) -> None:
    pkg = _make_valid_package(tmp_path)
    with open(pkg / "main.py", "a", encoding="utf-8") as f:
        f.write("tampered")
    problems = b.find_problems(pkg)
    assert any("size mismatch: main.py" in p for p in problems)


def test_check_detects_missing_required_file(tmp_path: Path) -> None:
    pkg = _make_valid_package(tmp_path)
    (pkg / "main.py").unlink()
    problems = b.find_problems(pkg)
    assert any("missing required file: main.py" in p for p in problems)


def test_check_detects_forbidden_path_marker(tmp_path: Path) -> None:
    pkg = _make_valid_package(tmp_path)
    _write(pkg / "config/recovery_password.json", b"{}")
    b.write_manifest(pkg)
    problems = b.find_problems(pkg)
    assert any("forbidden path marker" in p for p in problems)


def test_check_allows_runtime_generated_outputs(tmp_path: Path) -> None:
    pkg = _make_valid_package(tmp_path)
    _write(pkg / "reports/machine_scan.json", b"{}")
    _write(pkg / "logs/audit.log", b"log")
    _write(pkg / "Summary.xlsx", b"xls")
    _write(pkg / "config/__pycache__/settings.cpython-314.pyc", b"pyc")
    _write(pkg / "runtime/python/Lib/site-packages/psutil/__pycache__/__init__.cpython-314.pyc", b"pyc")
    problems = b.find_problems(pkg)
    assert problems == []


def test_check_detects_unexpected_non_generated_file(tmp_path: Path) -> None:
    pkg = _make_valid_package(tmp_path)
    _write(pkg / "stray_file.bin", b"x")
    problems = b.find_problems(pkg)
    assert any("unexpected shipped file: stray_file.bin" in p for p in problems)


def test_version_text_contains_required_fields(tmp_path: Path) -> None:
    text = b.version_text(REPO_ROOT)
    for field in ("Build Time UTC", "Git Commit ", "Git Commit Short", "Git Branch", "Git Worktree",
                  "Runtime Python", "Runtime Packages", "Runtime Zip SHA-256"):
        assert field in text


def test_runner_is_offline_safe() -> None:
    runner = b.RUNNER_SOURCE.read_text(encoding="utf-8", errors="replace")
    assert "EIMS_AUTO_SYNC=false" in runner
    assert "%~dp0runtime\\python\\python.exe" in runner
    assert "-B " in runner


def test_builder_never_formats_or_autoselects() -> None:
    ps1 = (b.TOOLS_DIR / "Build-EIMS-USB.ps1").read_text(encoding="utf-8", errors="replace")
    for dangerous in ("Format-Volume", "Initialize-Disk", "Clear-Disk", "format "):
        assert dangerous not in ps1
    assert "Read-Host 'Select drive index'" in ps1
    assert "'YES'" in ps1
    assert "$DriveLetter):\\EIMS_USB_Auditor" in ps1


def test_builder_wrappers_exist() -> None:
    bat = b.TOOLS_DIR / "Build-EIMS-USB.bat"
    ps1 = b.TOOLS_DIR / "Build-EIMS-USB.ps1"
    assert bat.is_file()
    assert ps1.is_file()
    body = ps1.read_text(encoding="utf-8", errors="replace")
    assert "DriveType = 2" in body
    assert "Read-Host" in body
    assert "EIMS_USB_Auditor" in body