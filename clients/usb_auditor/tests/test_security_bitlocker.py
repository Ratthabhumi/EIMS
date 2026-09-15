"""Unit tests for the safe, read-only BitLocker audit.

Verifies that:
  1. The compliance verdicts map correctly for every real-world state.
  2. No recovery-password material can ever survive into the report schema,
     including adversarial output from PowerShell.
"""

import json

import pytest

from scanner import security as sec

FAKE_RECOVERY_PASSWORD = "000000-000000-000000-000000-000000-000000-000000-000000"

FULLY_ENCRYPTED_OUTPUT = (
    "BITLOCKER_AVAILABLE=True\n"
    "VolumeStatus=FullyEncrypted\n"
    "ProtectionStatus=On\n"
    "EncryptionPercentage=100\n"
    "EncryptionMethod=XtsAes256\n"
    "RecoveryProtectorCount=1\n"
    "TpmPresent=True\n"
    "TpmReady=True\n"
)


def _evaluate(output: str = FULLY_ENCRYPTED_OUTPUT, fields_override: dict | None = None) -> dict:
    fields = sec._parse_bitlocker_output(output)
    if fields_override:
        fields.update(fields_override)
    return sec._evaluate_bitlocker(fields)


# ── Verdict mapping ──────────────────────────────────────────────────────────

def test_fully_compliant_machine():
    result = _evaluate()
    assert result["status"] == "PASS"
    assert result["protection_status"] == "On"
    assert result["volume_status"] == "FullyEncrypted"
    assert result["encryption_percentage"] == 100
    assert result["recovery_protector_present"] is True
    assert result["recovery_protector_count"] == 1


def test_protection_off_fully_encrypted():
    result = _evaluate(fields_override={"protection_status": "Off"})
    assert result["status"] == "FAIL"


def test_encryption_in_progress():
    result = _evaluate(fields_override={
        "volume_status": "EncryptionInProgress",
        "encryption_percentage": 45,
    })
    assert result["status"] == "WARNING"
    assert "in progress" in result["detail"]


def test_fully_unencrypted():
    result = _evaluate(fields_override={
        "volume_status": "FullyDecrypted",
        "protection_status": "Off",
        "encryption_percentage": 0,
    })
    assert result["status"] == "FAIL"


def test_missing_recovery_protector():
    result = _evaluate(fields_override={"recovery_protector_count": 0})
    assert result["status"] == "WARNING"
    assert "no recovery protector" in result["detail"]


def test_bitlocker_unavailable_defaults_fail():
    result = _evaluate("")
    assert result["status"] == "FAIL"
    assert result["protection_status"] == "Unavailable"


def test_unknown_protection_warns():
    result = _evaluate(fields_override={
        "protection_status": "Unknown",
        "volume_status": "Unknown",
    })
    assert result["status"] == "WARNING"


def test_decryption_in_progress_fails():
    result = _evaluate(fields_override={"volume_status": "DecryptionInProgress"})
    assert result["status"] == "FAIL"


def test_multiple_recovery_protectors_counted():
    result = _evaluate(fields_override={"recovery_protector_count": 3})
    assert result["status"] == "PASS"
    assert result["recovery_protector_count"] == 3


# ── Secret regression (report schema) ────────────────────────────────────────

@pytest.mark.parametrize("variant", [
    {},                              # fully compliant
    {"protection_status": "Off"},    # protection off
    {"volume_status": "EncryptionInProgress", "encryption_percentage": 45},
    {"protection_status": "Unknown", "volume_status": "Unknown"},
    {"recovery_protector_count": 0},
])
def test_report_schema_has_no_secret_keys(variant):
    result = _evaluate(fields_override=variant)
    keys = {k.lower() for k in result}
    assert "recovery_key" not in keys
    assert "recovery_password" not in keys
    assert "recoverypassword" not in keys
    serialized = json.dumps(result)
    assert "recovery_key" not in serialized
    assert "recovery_password" not in serialized


def test_parse_discards_adversarial_secret_line():
    adversarial = FULLY_ENCRYPTED_OUTPUT + f"\nRecoveryPassword={FAKE_RECOVERY_PASSWORD}\n"
    fields = sec._parse_bitlocker_output(adversarial)
    assert "RecoveryPassword" not in fields
    assert FAKE_RECOVERY_PASSWORD not in repr(fields)
    assert all(FAKE_RECOVERY_PASSWORD not in str(v) for v in fields.values())


def test_full_pipeline_never_exposes_secret(monkeypatch):
    adversarial = FULLY_ENCRYPTED_OUTPUT + f"\nRecoveryPassword={FAKE_RECOVERY_PASSWORD}\n"

    def _fake_powershell(command, timeout=10):
        return adversarial

    monkeypatch.setattr(sec, "_run_powershell", _fake_powershell)
    result = sec._check_bitlocker()

    assert "recovery_key" not in result
    assert "recovery_password" not in result
    assert FAKE_RECOVERY_PASSWORD not in json.dumps(result)


def test_powershell_command_never_retrieves_secret():
    cmd = sec._BITLOCKER_PS_COMMAND
    assert "ExpandProperty RecoveryPassword" not in cmd
    assert "select recoverypassword" not in cmd.lower()
    assert "$_.RecoveryPassword" not in cmd
    assert "recovery_key" not in cmd
    # The type-name filter is the only permitted mention of the protector type.
    assert "KeyProtectorType -eq 'RecoveryPassword'" in cmd


def test_excel_exporter_strips_legacy_secrets():
    from exporters.excel_exporter import _strip_secret_keys

    legacy = {
        "security": {
            "bitlocker": {
                "status": "PASS",
                "recovery_key": FAKE_RECOVERY_PASSWORD,
                "recovery_password": FAKE_RECOVERY_PASSWORD,
            }
        },
        "list": [{"recovery_key": FAKE_RECOVERY_PASSWORD}],
    }
    cleaned = _strip_secret_keys(legacy)
    serialized = json.dumps(cleaned)
    assert FAKE_RECOVERY_PASSWORD not in serialized
    assert "recovery_key" not in serialized
    assert "recovery_password" not in serialized
    assert cleaned["security"]["bitlocker"]["status"] == "PASS"


@pytest.mark.parametrize("secret_key, kept_value", [
    ("Recovery_Key", "legacy-secret"),
    ("RECOVERY_KEY", "legacy-secret"),
    ("recovery_key", "legacy-secret"),
    ("RecoveryPassword", FAKE_RECOVERY_PASSWORD),
    ("RECOVERYPASSWORD", FAKE_RECOVERY_PASSWORD),
    ("recovery_password", FAKE_RECOVERY_PASSWORD),
    ("Recovery_Password", FAKE_RECOVERY_PASSWORD),
])
def test_strip_secret_keys_is_case_insensitive(secret_key, kept_value):
    from exporters.excel_exporter import _strip_secret_keys

    report = {"security": {"bitlocker": {secret_key: kept_value, "status": "PASS"}}}
    cleaned = _strip_secret_keys(report)
    serialized = json.dumps(cleaned)
    assert kept_value not in serialized
    assert secret_key not in serialized
    assert cleaned["security"]["bitlocker"]["status"] == "PASS"


def test_strip_preserves_safe_recovery_metadata():
    from exporters.excel_exporter import _strip_secret_keys

    report = {
        "security": {
            "bitlocker": {
                "status": "PASS",
                "recovery_protector_present": True,
                "recovery_protector_count": 1,
                "RecoveryPassword": FAKE_RECOVERY_PASSWORD,
                "RECOVERY_KEY": "legacy-secret",
            }
        }
    }
    cleaned = _strip_secret_keys(report)
    bl = cleaned["security"]["bitlocker"]
    assert bl["recovery_protector_present"] is True
    assert bl["recovery_protector_count"] == 1
    serialized = json.dumps(cleaned)
    assert FAKE_RECOVERY_PASSWORD not in serialized
    assert "legacy-secret" not in serialized


def test_excel_columns_never_reference_secret_paths():
    from exporters.excel_exporter import COLUMNS, _SECRET_KEY_LOOKUP

    for header, json_path, _ in COLUMNS:
        for key in json_path:
            assert str(key).lower() not in _SECRET_KEY_LOOKUP, (
                f"column '{header}' references secret key '{key}'"
            )
    assert "BitLocker Key" not in [c[0] for c in COLUMNS]