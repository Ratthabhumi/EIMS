"""
tools/build_usb_package.py — verified portable USB Auditor package builder.

Assembles the portable package under dist/usb-auditor/EIMS_USB_Auditor:
  - Explicit source allowlist from clients/usb_auditor (never a directory copy)
  - Embedded CPython runtime (runtime/python) with exactly psutil + openpyxl
  - Run-EIMS-Audit.bat target runner
  - VERSION.txt (git provenance) and MANIFEST.txt (path | size | sha256)

Usage:
    python tools/build_usb_package.py --build [--offline]
    python tools/build_usb_package.py --check <package_dir>
    python tools/build_usb_package.py --show-allowlist

Exit codes: 0 = success, 2 = error.
Build-time network is only needed once to create the runtime cache; the
finished package is fully offline at audit time.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
SOURCE_ROOT = REPO_ROOT / "clients" / "usb_auditor"

CPU_ARCH = "amd64"
RUNTIME_VERSION = "3.14.3"
PY_SO_VERSION = "".join(RUNTIME_VERSION.split(".")[:2])
EMBED_URL = (
    f"https://www.python.org/ftp/python/{RUNTIME_VERSION}/"
    f"python-{RUNTIME_VERSION}-embed-{CPU_ARCH}.zip"
)
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
RUNTIME_PINS = ("psutil==7.2.2", "openpyxl==3.1.5")

STAGE_ROOT = REPO_ROOT / "dist" / "usb-auditor"
RUNTIME_ROOT = STAGE_ROOT / "runtime" / "python"
PACKAGE_DIR = STAGE_ROOT / "EIMS_USB_Auditor"
RUNTIME_COMPLETE_MARKER = RUNTIME_ROOT / ".portal-runtime.complete"
ZIP_SHA_FILE = STAGE_ROOT / "scripts" / f"python-{RUNTIME_VERSION}-embed-{CPU_ARCH}.zip.sha256"

RUNNER_SOURCE = TOOLS_DIR / "Run-EIMS-Audit.bat"

SOURCE_ALLOWLIST: tuple[str, ...] = (
    "main.py",
    "requirements.txt",
    "config/settings.py",
    "exporters/__init__.py",
    "exporters/excel_exporter.py",
    "exporters/json_exporter.py",
    "scanner/__init__.py",
    "scanner/compliance.py",
    "scanner/event_logs.py",
    "scanner/registry.py",
    "scanner/security.py",
    "scanner/services.py",
    "scanner/setup_verify.py",
    "scanner/system_info.py",
    "sync/__init__.py",
    "sync/eims_sync.py",
)

REQUIRED_PACKAGE_FILES: tuple[str, ...] = (
    "main.py",
    "Run-EIMS-Audit.bat",
    "VERSION.txt",
    "MANIFEST.txt",
    "config/settings.py",
    "scanner/security.py",
    "sync/eims_sync.py",
    "runtime/python/python.exe",
)

GENERATED_OUTPUT_NAMES = ("reports", "logs", "Summary.xlsx")

FORBIDDEN_PATH_MARKERS: tuple[str, ...] = (
    "recovery_password",
    "recoverypassword",
    "recovery_key",
    ".env",
    "id_rsa",
    "id_ed25519",
    "ssh_private",
    ".pem",
    ".pfx",
    ".p12",
    "credential",
)


def _sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def version_text(repo_root: Path, runtime_sha: str | None = None) -> str:
    commit = _git(repo_root, ["rev-parse", "HEAD"])
    branch = _git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    porcelain = _git(repo_root, ["status", "--porcelain"])
    if not commit and not branch:
        commit = "Unknown"
        worktree = "Unknown"
    else:
        worktree = "DIRTY" if porcelain else "CLEAN"
    commit_short = commit[:12] if commit and commit != "Unknown" else "Unknown"
    lines = [
        "EIMS Portable USB Auditor",
        "Build Time UTC     : " + datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "Git Commit         : " + commit,
        "Git Commit Short   : " + commit_short,
        "Git Branch         : " + branch,
        "Git Worktree       : " + worktree,
        f"Runtime Python     : {RUNTIME_VERSION} ({CPU_ARCH} embed)",
        "Runtime Packages   : " + ", ".join(sorted(RUNTIME_PINS)),
        "Runtime Zip SHA-256: " + (runtime_sha or "n/a"),
    ]
    return "\n".join(lines) + "\n"


def build_manifest(package_dir: Path) -> list[tuple[str, int, str]]:
    records: list[tuple[str, int, str]] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package_dir).as_posix()
        if rel == "MANIFEST.txt":
            continue
        records.append((rel, path.stat().st_size, _sha256_hex(path)))
    return records


def write_manifest(package_dir: Path) -> None:
    records = build_manifest(package_dir)
    lines = [
        "# EIMS Portable USB Auditor manifest (relative path | size | sha256)",
        "# Rebuild this file with: python tools/build_usb_package.py --build",
        "--- files ---",
    ]
    for rel, size, sha in records:
        lines.append(f"{rel} | {size} | {sha}")
    (package_dir / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_manifest(manifest_path: Path) -> dict[str, tuple[int, str]]:
    records: dict[str, tuple[int, str]] = {}
    if not manifest_path.is_file():
        return records
    in_files = False
    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\r")
        if line.strip() == "--- files ---":
            in_files = True
            continue
        if not in_files or not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3:
            rel, size, sha = parts
            records[rel] = (int(size), sha)
    return records


def _is_generated_output(rel: str) -> bool:
    for name in GENERATED_OUTPUT_NAMES:
        if rel == name or rel.startswith(name + "/"):
            return True
    return False


def _is_bytecode(rel: str) -> bool:
    parts = rel.split("/")
    return "__pycache__" in parts or rel.endswith(".pyc")


def find_problems(package_dir: Path) -> list[str]:
    package_dir = Path(package_dir).resolve()
    problems: list[str] = []
    manifest_path = package_dir / "MANIFEST.txt"
    if not manifest_path.is_file():
        return ["missing MANIFEST.txt"]
    records = parse_manifest(manifest_path)
    if not records:
        problems.append("MANIFEST.txt contains no file records")

    for required in REQUIRED_PACKAGE_FILES:
        if not (package_dir / Path(required)).is_file():
            problems.append(f"missing required file: {required}")

    for rel, (size, sha) in sorted(records.items()):
        path = package_dir / rel
        if not path.is_file():
            problems.append(f"missing manifest entry: {rel}")
            continue
        if path.stat().st_size != size:
            problems.append(f"size mismatch: {rel}")
            continue
        if _sha256_hex(path) != sha:
            problems.append(f"hash mismatch: {rel}")

    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package_dir).as_posix()
        if rel == "MANIFEST.txt" or _is_generated_output(rel) or _is_bytecode(rel):
            continue
        if rel not in records:
            problems.append(f"unexpected shipped file: {rel}")

    for rel in sorted(records):
        lowered = rel.lower()
        if any(marker in lowered for marker in FORBIDDEN_PATH_MARKERS):
            problems.append(f"forbidden path marker: {rel}")

    return problems


def _ensure_runtime(offline: bool) -> str | None:
    if RUNTIME_COMPLETE_MARKER.is_file():
        print(f"[OK]   Runtime cache present: {RUNTIME_ROOT}")
        return None
    if offline:
        raise SystemExit(
            "[FAIL] Runtime cache is missing and --offline was set. "
            "Run once with network access to create the embedded runtime."
        )
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

    zip_path = STAGE_ROOT / "scripts" / f"python-{RUNTIME_VERSION}-embed-{CPU_ARCH}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[..]   Downloading {EMBED_URL}")
    try:
        with urllib.request.urlopen(EMBED_URL, timeout=120) as resp:
            data = resp.read()
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"[FAIL] Could not download embedded Python: {exc}") from exc
    zip_sha = hashlib.sha256(data).hexdigest()
    zip_path.write_bytes(data)
    ZIP_SHA_FILE.write_text(zip_sha + "\n", encoding="ascii")

    print("[..]   Extracting embedded Python")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(RUNTIME_ROOT)

    pth = _find_pth(RUNTIME_ROOT, PY_SO_VERSION)
    pth.write_text(
        f"python{PY_SO_VERSION}.zip\n.\n..\\..\nLib\\site-packages\nimport site\n",
        encoding="utf-8",
    )

    get_pip = STAGE_ROOT / "scripts" / "get-pip.py"
    print(f"[..]   Downloading {GET_PIP_URL}")
    try:
        with urllib.request.urlopen(GET_PIP_URL, timeout=120) as resp:
            get_pip.write_bytes(resp.read())
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"[FAIL] Could not download get-pip.py: {exc}") from exc

    python_exe = RUNTIME_ROOT / "python.exe"
    print("[..]   Bootstrapping pip")
    _run_silent([str(python_exe), str(get_pip), "--no-warn-script-location"], timeout=600)
    print("[..]   Installing runtime packages")
    _run_silent(
        [str(python_exe), "-m", "pip", "install", "--no-warn-script-location", *RUNTIME_PINS],
        timeout=600,
    )
    print("[..]   Pruning bootstrap artifacts")
    _prune_clean(RUNTIME_ROOT)
    RUNTIME_COMPLETE_MARKER.write_text("complete\n", encoding="ascii")
    print(f"[OK]   Runtime ready: {RUNTIME_ROOT}")
    return zip_sha


def _find_pth(runtime_root: Path, so_version: str) -> Path:
    candidates = list(runtime_root.glob(f"python{so_version}._pth"))
    if candidates:
        return candidates[0]
    raise SystemExit(f"[FAIL] python{so_version}._pth not found in embedded runtime")


def _run_silent(argv: list[str], timeout: int) -> None:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"[FAIL] Command failed to start: {argv[0]} -> {exc}") from exc
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-10:] + result.stderr.splitlines()[-10:])
        raise SystemExit(f"[FAIL] Command exited {result.returncode}: {argv[0]}\n{tail}")


def _prune_clean(runtime_root: Path) -> None:
    site_packages = runtime_root / "Lib" / "site-packages"
    if site_packages.is_dir():
        for entry in list(site_packages.iterdir()):
            name = entry.name.lower()
            if name.startswith("pip") or name.startswith("setuptools") or name.startswith("wheel"):
                shutil.rmtree(entry, ignore_errors=True) if entry.is_dir() else entry.unlink()
    for cache_dir in runtime_root.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)


def _cached_zip_sha() -> str | None:
    if ZIP_SHA_FILE.is_file():
        value = ZIP_SHA_FILE.read_text(encoding="ascii").strip()
        return value or None
    return None


def build_package(offline: bool = False) -> str | None:
    print("[..]   Preparing embedded runtime")
    runtime_sha = _ensure_runtime(offline) or _cached_zip_sha()

    print(f"[..]   Staging package: {PACKAGE_DIR}")
    if PACKAGE_DIR.is_dir():
        print("[..]   Replacing previous staged build (full rebuild)")
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    missing = [rel for rel in SOURCE_ALLOWLIST if not (SOURCE_ROOT / Path(rel)).is_file()]
    if missing:
        raise SystemExit(f"[FAIL] Allowlisted source files missing: {', '.join(missing)}")

    for rel in SOURCE_ALLOWLIST:
        src = SOURCE_ROOT / Path(rel)
        dst = PACKAGE_DIR / Path(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    if not RUNNER_SOURCE.is_file():
        raise SystemExit(f"[FAIL] Runner missing: {RUNNER_SOURCE}")
    shutil.copy2(RUNNER_SOURCE, PACKAGE_DIR / "Run-EIMS-Audit.bat")

    shutil.copytree(RUNTIME_ROOT, PACKAGE_DIR / "runtime" / "python", dirs_exist_ok=True)
    (PACKAGE_DIR / "runtime" / "python" / RUNTIME_COMPLETE_MARKER.name).unlink(missing_ok=True)

    (PACKAGE_DIR / "VERSION.txt").write_text(version_text(REPO_ROOT, runtime_sha), encoding="utf-8")
    write_manifest(PACKAGE_DIR)

    problems = find_problems(PACKAGE_DIR)
    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}")
        raise SystemExit(2)

    records = parse_manifest(PACKAGE_DIR / "MANIFEST.txt")
    total = sum(size for size, _ in records.values())
    print(f"[OK]   Package verified: {len(records)} files, {total} bytes")
    print(f"[OK]   Staged at: {PACKAGE_DIR}")
    return str(PACKAGE_DIR)


def _main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Build or verify the portable USB Auditor package.")
    parser.add_argument("--build", action="store_true", help="assemble dist/usb-auditor/EIMS_USB_Auditor")
    parser.add_argument("--check", metavar="DIR", help="verify an existing package directory")
    parser.add_argument("--offline", action="store_true", help="never download (uses cached runtime)")
    parser.add_argument("--show-allowlist", action="store_true", help="print the source allowlist")
    args = parser.parse_args(argv)

    if args.show_allowlist:
        for rel in SOURCE_ALLOWLIST:
            print(rel)
        return 0
    if args.check:
        problems = find_problems(Path(args.check))
        if problems:
            for problem in problems:
                print(f"[FAIL] {problem}")
            return 2
        records = parse_manifest(Path(args.check) / "MANIFEST.txt")
        print(f"PACKAGE OK ({len(records)} files)")
        return 0
    if args.build:
        build_package(offline=args.offline)
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())