"""Backend guidance JSON -> the real React panel (server-side render). Skipped, not passed, when node or the dashboard dependencies are absent."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.domain.analyzer.services import catalog_diagnostics as cd
from tests.certification_fixtures import ASA_POSITIVE, pg_json

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None or not (ROOT / "clients" / "dashboard" / "node_modules" / "react-dom").exists(),
                                reason="node or dashboard dependencies not installed")


def render(tmp_path, cases):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "analyzer_guidance_ui.cjs"), str(src)], capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout)


def guidance(family, text):
    return cd.catalog_summary(family, text, "en").operationalGuidance.model_dump()


def test_all_twelve_sections_render_with_server_assigned_statuses(tmp_path):
    cases = {"eligible": guidance("cisco_asa", ASA_POSITIVE["113005"]), "missing_recovery": guidance("json", pg_json("40P01"))}
    report = render(tmp_path, cases)
    ids = {"g-what", "g-why", "g-inspect", "g-action", "g-permission", "g-risk", "g-approval", "g-rollback", "g-recovery", "g-source", "g-version", "g-limits"}
    assert set(report["eligible"]["rows"]) == ids == set(report["missing_recovery"]["rows"])
    assert report["eligible"]["rows"]["g-recovery"] == "stated" and report["eligible"]["rows"]["g-source"] == "stated"
    assert report["missing_recovery"]["rows"]["g-recovery"] == "not_stated"          # shown as NOT STATED, never filled in
    assert report["missing_recovery"]["rows"]["g-rollback"] == "not_stated" and "NOT STATED" in report["missing_recovery"]["html"]
    assert report["eligible"]["pendingBanner"] and report["missing_recovery"]["pendingBanner"]   # nothing looks approved


def test_unverified_items_are_flagged_and_never_shown_as_confirmed(tmp_path):
    g = guidance("json", pg_json("40P01"))
    g["recoveryVerification"] = {"status": "unverified", "items": ["Re-run the monitoring query."], "basis": "composed", "source": "", "origin": ""}
    report = render(tmp_path, {"unverified": g})["unverified"]
    assert report["rows"]["g-recovery"] == "unverified" and report["unverifiedNotice"] and "UNVERIFIED" in report["html"]


def test_destructive_action_without_rollback_shows_a_warning(tmp_path):
    g = guidance("json", pg_json("40P01"))
    g["destructiveActions"] = ["Drop the replication slot."]
    g["rollback"] = {"status": "not_stated", "items": [], "source": "", "basis": "", "origin": ""}
    report = render(tmp_path, {"warn": g})["warn"]
    assert report["destructiveWarning"] and 'role="alert"' in report["html"]
    g["rollback"] = {"status": "stated", "items": ["Recreate the slot."], "source": "https://x", "basis": "", "origin": ""}
    assert not render(tmp_path, {"ok": g})["ok"]["destructiveWarning"]


def test_reference_only_or_missing_guidance_renders_nothing(tmp_path):
    reference_only = cd.catalog_summary("json", pg_json("23505"), "en").operationalGuidance
    assert reference_only is None
    report = render(tmp_path, {"none": None, "no_id": {"whatHappened": "x"}})
    assert report["none"]["html"] == "" and report["no_id"]["html"] == ""


def test_eims_policy_origin_is_labelled_not_attributed_to_the_vendor(tmp_path):
    g = guidance("json", pg_json("40P01"))
    g["humanApproval"] = {"status": "stated", "items": ["Destructive actions require explicit human approval before execution (EIMS policy)."],
                          "source": "EIMS policy", "basis": "", "origin": "eims_policy"}
    report = render(tmp_path, {"policy": g})["policy"]
    assert "not a vendor statement" in report["html"]
