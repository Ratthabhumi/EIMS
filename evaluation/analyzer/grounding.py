"""Claim-role records and human support judgments, never keyword hallucination scores."""
import json
from evaluation.analyzer.scoring import ratio


def review_queue(predictions):
    return {"schema_version": "2.0", "judgments": [
        {"case_id": p["case_id"], "prediction_sha256": p["prediction_sha256"],
         "claim_id": c["claim_id"], "text": c["text"], "claim_category": c["category"],
         "evidence": [{"file": r["file"], "line": r["line"], "evidence_type": c["evidence_type"]}
                      for r in c["evidence"]],
         "support_judgment": "NOT_REVIEWED", "reviewer": None, "rationale": None}
        for p in predictions if p["status"] == "OK" for c in p.get("claims", [])]}


def validate_reviews(doc, predictions, payloads):
    from pathlib import Path
    import jsonschema
    schema = json.loads(Path(__file__).with_name("grounding.v2.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)
    by_id = {p["case_id"]: p for p in predictions}
    seen = set()
    for r in doc["judgments"]:
        p = by_id.get(r["case_id"])
        claims = {c["claim_id"]: c for c in p.get("claims", [])} if p else {}
        key = (r["case_id"], r["claim_id"])
        if key in seen or not p or r["prediction_sha256"] != p.get("prediction_sha256"):
            raise ValueError("duplicate/stale grounding review")
        seen.add(key)
        if r["claim_id"] not in claims or claims[r["claim_id"]]["text"] != r["text"]:
            raise ValueError("grounding review does not name an emitted claim")
        if r["support_judgment"] != "NOT_REVIEWED" and (
                not r["reviewer"] or r["reviewer"].lower().startswith(("ai", "codex")) or not r["rationale"]):
            raise ValueError("human support judgment requires actual reviewer and rationale")
        for ref in r["evidence"]:
            files = payloads[r["case_id"]]
            if ref["file"] not in files or not 1 <= ref["line"] <= ref.get("end_line", ref["line"]) <= len(files[ref["file"]][1].splitlines()):
                raise ValueError("grounding evidence does not exist in exact source")
    return doc


def score_grounding(doc, predictions):
    judged = [r for r in doc["judgments"] if r["support_judgment"] in {"SUPPORTED", "UNSUPPORTED"}]
    unsupported = [r for r in judged if r["support_judgment"] == "UNSUPPORTED"]
    all_claims = sum(len(p.get("claims", [])) for p in predictions)
    return {"emitted_claims": all_claims, "reviewed_binary_judgments": len(judged),
            "uncertain_judgments": sum(r["support_judgment"] == "UNCERTAIN" for r in doc["judgments"]),
            "semantic_support_precision": ratio(len(judged) - len(unsupported), len(judged), len({r["case_id"] for r in judged}), "actual human claim-to-evidence support judgments only"),
            "unsupported_claim_rate": ratio(len(unsupported), len(judged), len({r["case_id"] for r in judged}), "unsupported / binary judged material claims; not a keyword proxy"),
            "review_coverage": ratio(len(judged), all_claims, len(predictions), "human-judged subset / all emitted claim records"),
            "failures": [{k: r[k] for k in ("case_id", "claim_id", "text", "evidence", "reviewer", "rationale")} for r in unsupported],
            "status": "NOT_MEASURED" if not judged else "REVIEWED_SUBSET_ONLY"}
