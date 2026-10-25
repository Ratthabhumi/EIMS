"""Create an offline synthetic Veeam/VMware investigation and source inspector."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.analyzer.runner import digest, git, validate_output
from evaluation.analyzer.investigation import predict_full
from evaluation.analyzer.semantics_v2 import project
from evaluation.analyzer.inspection import render


def hero_inputs():
    veeam = """[2026-10-25T10:00:00Z] Info [Veeam.Backup.Core] Synthetic replica task started
[2026-10-25T10:00:02Z] Error [CViSnapReplica] Could not delete change tracking file fileName='/vmfs/volumes/demo/demo.vmdk'
[2026-10-25T10:00:05Z] Error [Veeam.Backup.Core] Task session 'demo-session-only' has been completed, status: 'Failed'
"""
    vmware = """2026-10-25T10:00:01Z Er(02) vmx - VMware DISKLIB-CTK: Could not delete change tracking file fileName='/vmfs/volumes/demo/demo.vmdk'
2026-10-25T10:00:03Z Er(02) vmx - CTK_CTKUNLINK result:2620
"""
    return {n: (t.encode(), t) for n, t in (("a-veeam.txt", veeam), ("b-vmware.txt", vmware))}


def create(output):
    output = validate_output(output)
    files = hero_inputs()
    case = {"case_id": "synthetic_veeam_vmware_demo", "files": [{"path": n} for n in files]}
    p = predict_full(case, files)
    p["semantics_v2"] = project(p, files)
    p["prediction_sha256"] = digest(p)
    output.mkdir(parents=True, exist_ok=False)
    (output / "investigation.json").write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "history_snapshot.json").write_text(json.dumps(p["isolated_history_snapshot"], indent=2) + "\n", encoding="utf-8")
    (output / "inspector.html").write_text(render(p, files), encoding="utf-8")
    config = {"source_sha": git("rev-parse", "HEAD"), "case_status": "DRAFT_DEMO_ONLY_NOT_GOLD",
              "input_sha256": {n: hashlib.sha256(raw).hexdigest() for n, (raw, _) in files.items()},
              "no_operational_storage": True, "external_network": "BLOCKED"}
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    for name, (raw, _) in files.items():
        (output / name).write_bytes(raw)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prediction = create(args.output)
    print("DRAFT_SYNTHETIC_DEMO", prediction["native_response"]["correlationConfidence"],
          "isolated_history_roundtrip=", prediction["isolated_history_roundtrip"])
