"""Add an ``applicability`` block to Windows catalog records from the source research ledger (dry-run by default).

Only text published by the cited official page is copied (verbatim). Nothing is inferred from OS versions, file dates or
documentation versions. Records the ledger could not support are left untouched. The edit is text-level, preserves the
file's line endings and every other byte, and is idempotent.
Block fields: kind (os_versions_as_stated_by_page | product_level_statement_only), statement, event_versions (schema versions,
kept separate), source_url, source_title, publication (page metadata, not OS support), retrieved, status.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "backend" / "domain" / "analyzer" / "services" / "operational_event_catalog.json"
LEDGER = ROOT / "docs" / "acceptance" / "certification" / "windows_source_research_ledger.json"
KIND = {"EXPLICIT_OS_STATEMENT_FOUND": "os_versions_as_stated_by_page", "PRODUCT_LEVEL_APPLICABILITY_ONLY": "product_level_statement_only"}


def plan(ledger: dict) -> dict[tuple[str, str], dict]:
    chosen: dict[tuple[str, str], dict] = {}
    disp = {d["record_key"]: d["ledger_disposition"] for d in ledger["dispositions"]}
    for row in ledger["rows"]:
        want = disp.get(row["record_key"])
        if row["source_kind"] != "cited_in_catalog" or want not in KIND or row["automated_status"] != want:
            continue
        key = (row["event_id"], row["provider"])
        if key in chosen:
            continue
        explicit = want == "EXPLICIT_OS_STATEMENT_FOUND"
        chosen[key] = {
            "kind": KIND[want], "statement": row["os_statement"] if explicit else row["applies_to_statement"],
            "event_versions": row["event_versions_statement"] if explicit else "",
            "source_url": row["source_url"], "source_title": row["source_title"],
            "publication": {"ms_date": row["pub_ms_date"], "updated_at": row["pub_updated_at"], "git_commit": row["pub_git_commit"]},
            "retrieved": row["retrieval_date"], "status": "official_text_extracted_human_reread_pending",
        }
    return chosen


def apply(text: str, chosen: dict[tuple[str, str], dict]) -> tuple[str, int]:
    nl = "\r\n" if "\r\n" in text else "\n"
    tail = nl + "  }"
    start = text.index("[") + 1
    decoder = json.JSONDecoder()
    out, pos, count, idx = [text[:start]], start, 0, start
    while True:
        while idx < len(text) and text[idx] in " \n\r\t,":
            idx += 1
        if idx >= len(text) or text[idx] == "]":
            break
        obj, end = decoder.raw_decode(text, idx)
        raw = text[idx:end]
        key = (obj.get("event_id"), obj.get("provider"))
        if key in chosen and "applicability" not in obj:
            assert raw.endswith(tail), "unexpected record layout"
            raw = raw[: -len(tail)] + "," + nl + '    "applicability": ' + json.dumps(chosen[key], ensure_ascii=False) + tail
            count += 1
        out.append(text[pos:idx])
        out.append(raw)
        pos = end
        idx = end
    out.append(text[pos:])
    return "".join(out), count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    chosen = plan(json.loads(LEDGER.read_text(encoding="utf-8")))
    with CATALOG.open(encoding="utf-8", newline="") as fh:  # keep the file's line endings
        text = fh.read()
    new_text, count = apply(text, chosen)
    json.loads(new_text)  # must stay valid JSON
    kinds: dict[str, int] = {}
    for c in chosen.values():
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(json.dumps({"planned": len(chosen), "newly_applied": count, "by_kind": kinds, "mode": "apply" if args.apply else "dry-run"}))
    if args.apply and count:
        with CATALOG.open("w", encoding="utf-8", newline="") as fh:
            fh.write(new_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
