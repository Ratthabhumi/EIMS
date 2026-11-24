"""Obsidian export must not let parsed log content shape file paths (hermetic; temp vault only)."""
import os

import pytest

from backend.domain.analyzer.services import obsidian


@pytest.mark.parametrize("event_id", [
    "../../escape", "..\\..\\escape", "C:\\Windows\\x", "1129:stream", "a/b", "x" * 500, "", None, "ภาษาไทย",
])
def test_event_id_cannot_escape_or_shape_the_vault_path(tmp_path, monkeypatch, event_id):
    vault = tmp_path / "vault"
    monkeypatch.setattr(obsidian, "VAULT_PATH", str(vault))
    path = obsidian.save_to_obsidian(event_id, "synthetic", {"overview": "o"})
    real = os.path.realpath(path)
    assert os.path.dirname(real) == os.path.realpath(str(vault))
    name = os.path.basename(real)
    assert name.startswith("Event_") and name.endswith(".md")
    assert not set(name) & set('/\\:')
    assert len(name) < 120
    assert sorted(p.name for p in tmp_path.iterdir()) == ["vault"]   # nothing written outside the vault
