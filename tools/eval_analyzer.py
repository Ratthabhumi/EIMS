"""Reproducible offline Analyzer evaluation. Defaults to reviewed cases only."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.analyzer.runner import run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("evaluation/analyzer/gold/manifest.v1.json"))
    parser.add_argument("--mode", choices=["rule_only", "rule_kb", "rag", "llm"], default="rule_only")
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--include-draft", action="store_true", help="exploratory dev smoke only, never reviewed gold")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--manual-reviews", type=Path, help="human support labels bound to exact predictions")
    args = parser.parse_args(argv)
    try:
        result = run(args.manifest.resolve(), args.mode, args.split, args.output.resolve(),
                     args.include_draft, args.repeats, args.warmups, args.manual_reviews)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"EVALUATION_REJECTED: {exc}\n")
    except ImportError:
        parser.exit(2, "EVALUATION_DEPENDENCY_MISSING: install requirements-evaluation.txt in the development environment\n")
    print(result["status"], result["composition"])
    return 1 if result["error_count"] or result["exploratory_draft_only"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
