"""Record an actual human annotation review; never run to manufacture review."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.analyzer.runner import annotation_digest, load_manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=Path("evaluation/analyzer/gold/manifest.v1.json"))
    p.add_argument("--case-id", required=True)
    p.add_argument("--reviewer-id", required=True, help="public-safe human reviewer alias, no personal data")
    p.add_argument("--confirm-human-review", action="store_true", required=True)
    p.add_argument("--annotations-v2", type=Path, help="review parallel v2 semantics only; never transfers review to v1")
    args = p.parse_args()
    doc, _ = load_manifest(args.manifest.resolve())
    if args.annotations_v2:
        from evaluation.analyzer.semantics_v2 import load_annotations, review_digest
        v2, cases = load_annotations(args.annotations_v2, args.manifest.resolve(), doc["cases"])
        if args.case_id not in cases:
            p.error("unknown v2 DEV case")
        if not args.reviewer_id.strip() or args.reviewer_id.strip().lower().startswith(("ai", "codex")):
            p.error("an actual human reviewer assertion is required")
        c = cases[args.case_id]
        c.update(review_status="REVIEWED", reviewer_id=args.reviewer_id,
                 reviewed_annotation_sha256=review_digest(c))
        args.annotations_v2.write_text(json.dumps(v2, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("Recorded human review assertion for v2 only:", args.case_id)
        return
    matches = [c for c in doc["cases"] if c["case_id"] == args.case_id]
    if not matches:
        p.error("unknown case")
    if not args.reviewer_id.strip() or args.reviewer_id.strip().lower().startswith(("ai", "codex")):
        p.error("reviewer must identify an actual human; confirmation is a recorded assertion, not authentication")
    c = matches[0]
    c.update(review_status="REVIEWED", reviewer_id=args.reviewer_id,
             reviewed_annotation_sha256=annotation_digest(c))
    args.manifest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("Recorded human review assertion for", args.case_id)


if __name__ == "__main__":
    main()
