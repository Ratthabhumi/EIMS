"""Static safety tests for the BitLocker remediation utility.

These tests do NOT execute the PowerShell script. They assert structural
guarantees so a future edit cannot silently add a dangerous operation:
no Enable/Disable/Add protector, no reboot, plan-only default, hard gating.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR = REPO_ROOT / "tools" / "bitlocker_remediation"

PS1 = TOOL_DIR / "Remediate-BitLocker.ps1"
BAT = TOOL_DIR / "Run-BitLocker-Remediation.bat"
README = TOOL_DIR / "README.md"

FORBIDDEN_OPERATIONS = [
    "Enable-BitLocker",
    "Disable-BitLocker",
    "Add-BitLockerKeyProtector",
    "Remove-BitLockerKeyProtector",
    "Export-BitLockerKeyPackage",
    "Clear-BitLockerAutoUnlock",
    "Restart-Computer",
    "shutdown",
    "manage-bde",
    "Select-String RecoveryPassword",
]

FORBIDDEN_SECRET_EXPRESSIONS = [
    "ExpandProperty RecoveryPassword",
    "$_.RecoveryPassword",
    ".RecoveryPassword",
    "recovery_key",
    "recovery_password",
]


def _ps1_text() -> str:
    return PS1.read_text(encoding="utf-8")


def _ps1_body() -> str:
    """Return the executable body only (comments/help header excluded)."""
    text = _ps1_text()
    return text.split("#>", 1)[1]


def test_script_exists():
    assert PS1.exists(), "Remediate-BitLocker.ps1 is missing"


def test_launcher_and_readme_exist():
    assert BAT.exists(), "Run-BitLocker-Remediation.bat is missing"
    assert README.exists(), "README.md is missing"


def test_default_is_plan_only():
    text = _ps1_text()
    assert "[switch]$Apply" in text
    assert "PLAN-ONLY" in text.upper()
    # The plan-only path must not call Resume-BitLocker.
    plan_only_branch = _ps1_body().split("# ── Plan-only path")[-1]
    assert "Resume-BitLocker" not in plan_only_branch


def test_apply_gated_by_admin():
    body = _ps1_body()
    assert "Test-IsAdministrator" in body
    assert "-Apply requires an Administrator shell" in body
    # Resume must appear only after the admin gate.
    resume_index = body.index("Resume-BitLocker")
    admin_gate_index = body.index("-Apply requires an Administrator shell")
    assert admin_gate_index < resume_index


def test_apply_gated_by_exact_confirmation():
    body = _ps1_body()
    assert '"REMEDIATE {0}"' in body
    assert "Read-Host" in body
    assert "$typed.Trim() -ne $expected" in body
    assert "confirmation did not match" in body.lower()


def test_confirmation_aborts_before_mutation():
    body = _ps1_body()
    abort_block = body.split("[ABORT]")[1].split("Write-AuditLine")[0]
    assert "Resume-BitLocker" not in abort_block


def test_forbidden_operations_absent():
    body = _ps1_body()
    for op in FORBIDDEN_OPERATIONS:
        assert op.lower() not in body.lower(), f"forbidden operation present: {op}"


def test_no_secret_material_in_script():
    body = _ps1_body()
    for expr in FORBIDDEN_SECRET_EXPRESSIONS:
        assert expr not in body, f"forbidden secret expression present: {expr}"
    # The KeyProtectorType filter is the ONLY mention of the protector type.
    assert "KeyProtectorType -eq 'RecoveryPassword'" in body


def test_only_permitted_mutation_is_resume():
    body = _ps1_body()
    mutations = [line.strip() for line in body.splitlines()
                 if line.strip().startswith(("Resume-BitLocker",
                                             "Enable-BitLocker",
                                             "Disable-BitLocker"))]
    assert all(line.startswith("Resume-BitLocker") for line in mutations)
    assert mutations, "expected at least one Resume-BitLocker call"


def test_never_automatic_reboot():
    body = _ps1_body()
    assert "NEVER restarts the machine" in body
    lower = body.lower()
    for token in ("restart-computer", "shutdown /r", "shutdown.exe", "wmic"):
        assert token not in lower, f"reboot token present: {token}"


def test_decision_matrix_all_cases_present():
    body = _ps1_body()
    for marker in (
        "'COMPLIANT'",
        "'RESUME_PROTECTION'",
        "'IN_PROGRESS'",
        "'BLOCKED'",
        "'ACTION_REQUIRED'",
        "'UNKNOWN'",
    ):
        assert marker in body, f"missing decision case marker: {marker}"


def test_no_web_trigger_surface():
    # The tool must not be importable/triggerable from the backend API.
    assert not (TOOL_DIR / "__init__.py").exists()
    assert "import-report" not in _ps1_body()
    assert "http" not in _ps1_body().lower()