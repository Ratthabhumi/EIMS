"""Windows (class A) source research ledger: verbatim, officially published applicability statements per record.

For every Windows record the ledger lists, per cited official page: the exact page title, publication metadata
(ms.date / updated_at / git commit), whether the Event ID really appears in the page text, and the page's *own* wording
about product, OS version, event versions (schema) and builds. Those five things are never merged:
  * documentation publication info  -> ``pub_*`` fields (about the page, not the OS)
  * OS version statement            -> ``os_statement`` (only text that names Windows releases)
  * product-level applicability     -> ``applies_to_statement`` (e.g. "Supported versions of Windows Client": not a range)
  * event schema versions           -> ``event_versions_statement``
  * Windows build                   -> ``build_mention`` (a build named anywhere on the page, e.g. for one update; NOT a support statement)
                                       and ``build_support_statement`` (always empty: no automated rule establishes build support)
For records without a direct source, official Microsoft Learn search results are fetched and kept as *candidates* with the
evidence snippet; a candidate is never adopted automatically. Nothing here is a human review.
Network is used (Microsoft Learn only). Pages are cached under --cache so reruns are deterministic.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICES = ROOT / "backend" / "domain" / "analyzer" / "services"
CERT = ROOT / "docs" / "acceptance" / "certification"
UA = {"User-Agent": "EIMS-source-readcheck/1.0"}
ALLOWED_HOSTS = ("learn.microsoft.com", "support.microsoft.com")
OS_WORDS = re.compile(r"\bWindows\s+(?:Server\s+)?(?:\d{4}(?:\s+R2)?|Vista|XP|[78](?:\.1)?|1[01])\b", re.I)
CHANNEL = {"Windows Security": "Security", "Windows System": "System", "Windows Application": "Application"}


def _fetch(url: str, cache: Path) -> str:
    f = cache / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if f.exists():
        return f.read_text(encoding="utf-8", errors="replace")
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read()
    f.write_bytes(raw)
    return raw.decode("utf-8", errors="replace")


def parse_page(raw: str) -> dict:
    metas = dict(re.findall(r'<meta name="([^"]+)" content="([^"]*)"', raw))
    title_m = re.search(r"<title>(.*?)</title>", raw, re.S)
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))
    return {"metas": metas, "title": re.sub(r"\s+", " ", html.unescape(title_m.group(1))).strip() if title_m else "", "text": text}


def extract(text: str, event_id: str) -> dict:
    out = {"applies_to_statement": "", "os_statement": "", "event_versions_statement": "", "product_version_field": "", "build_mention": "", "build_support_statement": ""}
    m = re.search(r"Applies to:\s*(.{1,220}?)(?=\s+(?:Feedback|Summarize this article|In this article|How do I|Note|Important|This article|Learn how))", text)
    if m:
        out["applies_to_statement"] = m.group(1).strip()
    m = re.search(r"\bVersion:\s*(.{1,900}?)(?=\s(?:Message:|Field Descriptions|Security Monitoring|Event XML|Symbolic|Description:|Engine Version:|Event ID\b))", text)
    if m:
        value = m.group(1).strip()
        if OS_WORDS.search(value):
            ev = re.search(r"Event Versions?:\s*(.+)$", value)
            out["os_statement"] = (value[: ev.start()] if ev else value).strip(" .")
            if ev:
                out["event_versions_statement"] = ev.group(1).strip()
        else:
            out["product_version_field"] = value
    m = re.search(r"\bBuild(?:s)?\s+(\d{4,5}(?:\.\d+)?)", text)
    if m and "Windows" in text[max(0, m.start() - 60): m.end() + 60]:
        out["build_mention"] = text[max(0, m.start() - 60): m.end() + 60].strip()  # a build named in a scenario/update, never a support statement
    return out


def id_context(text: str, event_id: str, provider_tokens: list[str]) -> tuple[bool, str, bool]:
    """(event id named in an event-like context, snippet, provider token also present on the page)."""
    pat = re.compile(rf"(?i)(?:event\s*(?:id)?|eventid|id)\W{{0,3}}{re.escape(event_id)}\b|\b{re.escape(event_id)}\s*[:(\u2013-]\s*[A-Z]"
                     rf"|\bevents?\s+(?:ids?\s+)?(?:\d{{1,6}}\s*(?:,|and|or)\s*){{0,6}}{re.escape(event_id)}\b")
    m = pat.search(text)
    low = text.lower()
    prov = any(t and t.lower() in low for t in provider_tokens)
    if not m:
        return False, "", prov
    return True, text[max(0, m.start() - 140): m.end() + 200].strip(), prov


def _tokens(rec: dict) -> list[str]:
    raw = [rec.get("provider", "")] + list(rec.get("provider_names", []))
    out = []
    for r in raw:
        r = re.sub(r"\s*\(.*?\)", "", str(r)).strip()
        out += [r, r.removeprefix("Microsoft-Windows-")]
    return [t for t in dict.fromkeys(out) if t and t not in ("Windows Security", "Windows System", "Windows Application")]


def _search(query: str, cache: Path) -> list[dict]:
    f = cache / ("search_" + hashlib.sha1(query.encode()).hexdigest() + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    url = "https://learn.microsoft.com/api/search?search=" + urllib.parse.quote(query) + "&locale=en-us&%24top=6"
    data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
    results = [{"title": r["title"], "url": r["url"]} for r in data.get("results", [])]
    f.write_text(json.dumps(results), encoding="utf-8")
    return results


def build(cache: Path) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    records = json.loads((SERVICES / "operational_event_catalog.json").read_text(encoding="utf-8"))
    from backend.domain.analyzer.services.operational_catalog import load_catalog
    keys = {(e["event_id"], e["provider"]): f"operational:{e['source_family']}:{e['code_type']}:{e.get('diagnostic_code', e['event_id'])}"
            for e in load_catalog() if e["source_family"] == "windows_event"}
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    win_disp = {(r["event_id"], r["provider"]): r for r in json.loads((SERVICES / "windows_reference_dispositions.json").read_text(encoding="utf-8"))["records"]}
    jobs = []
    for rec in records:
        for ref in rec.get("official_references", []):
            jobs.append((rec, ref["url"], "cited_in_catalog"))
        if not rec.get("official_references"):
            for q in (f"Event ID {rec['event_id']} {rec['provider']}", f"{rec['title']} event {rec['event_id']}"):
                for res in _search(q, cache)[:6]:
                    if urlparse_host(res["url"]) in ALLOWED_HOSTS and "/answers/" not in res["url"]:
                        jobs.append((rec, res["url"], "candidate_from_search"))
    uniq = sorted({u for _, u, _ in jobs})
    with ThreadPoolExecutor(6) as pool:
        pages = dict(zip(uniq, pool.map(lambda u: _safe(u, cache), uniq)))
    rows, seen, checked = [], set(), {}
    for rec, url, kind in jobs:
        if (rec["event_id"], rec["provider"], url) in seen:
            continue
        seen.add((rec["event_id"], rec["provider"], url))
        page = pages[url]
        key = keys[(rec["event_id"], rec["provider"])]
        base = {"record_key": key, "event_id": rec["event_id"], "provider": rec["provider"], "provider_names": rec.get("provider_names", []),
                "channel": CHANNEL.get(rec["provider"], ""), "channel_note": "" if rec["provider"] in CHANNEL else "channel is not recorded in the catalog",
                "source_kind": kind, "source_url": url, "retrieval_date": now}
        if page is None:
            rows.append({**base, "source_title": "", "pub_ms_date": "", "pub_updated_at": "", "pub_git_commit": "", "pub_origin": "", "event_id_in_page": False,
                         "provider_in_page": False, "evidence_snippet": "", "applies_to_statement": "", "os_statement": "", "event_versions_statement": "",
                         "product_version_field": "", "build_mention": "", "build_support_statement": "", "automated_status": "FETCH_FAILED",
                         "remaining_uncertainty": "page could not be retrieved"})
            continue
        ex = extract(page["text"], rec["event_id"])
        named, snippet, prov = id_context(page["text"], rec["event_id"], _tokens(rec))
        m = page["metas"]
        if not named:
            status = "EVENT_ID_NOT_IN_PAGE"
        elif ex["os_statement"]:
            status = "EXPLICIT_OS_STATEMENT_FOUND"
        elif ex["applies_to_statement"]:
            status = "PRODUCT_LEVEL_APPLICABILITY_ONLY"
        else:
            status = "NO_APPLICABILITY_STATEMENT"
        if kind == "candidate_from_search":
            status = "CANDIDATE_" + ("STRONG" if named and prov else "WEAK" if named else "NO_MATCH")
            if status == "CANDIDATE_NO_MATCH":
                checked.setdefault(key, []).append(url)
                continue
        unc = []
        if status.startswith("PRODUCT_LEVEL"):
            unc.append("page states product-level applicability only; no OS version or build range")
        if status == "NO_APPLICABILITY_STATEMENT":
            unc.append("page names the Event ID but states no applicability")
        if status == "EVENT_ID_NOT_IN_PAGE":
            unc.append("cited page does not name this Event ID in an event-like context; relation to the record must be confirmed by a human")
        if status.startswith("CANDIDATE"):
            unc.append("search candidate; not adopted into the catalog; human must read the page")
        unc.append("no Windows build support statement (a build mention on the page is scenario-specific)" if ex["build_mention"] else "no Windows build stated")
        rows.append({**base, "source_title": page["title"], "pub_ms_date": m.get("ms.date", ""), "pub_updated_at": m.get("updated_at", ""),
                     "pub_git_commit": m.get("git_commit_id", ""), "pub_origin": m.get("original_content_git_url", ""),
                     "event_id_in_page": named, "provider_in_page": prov, "evidence_snippet": snippet, **ex,
                     "automated_status": status, "remaining_uncertainty": "; ".join(unc)})
    # per-record disposition
    by_rec: dict[str, list[dict]] = {}
    for r in rows:
        by_rec.setdefault(r["record_key"], []).append(r)
    dispositions = []
    for rec in records:
        key = keys[(rec["event_id"], rec["provider"])]
        mine = by_rec.get(key, [])
        cited = [r for r in mine if r["source_kind"] == "cited_in_catalog"]
        cand = [r for r in mine if r["source_kind"] == "candidate_from_search" and r["automated_status"] == "CANDIDATE_STRONG"]
        if cited:
            ok = [r for r in cited if r["automated_status"] in ("EXPLICIT_OS_STATEMENT_FOUND", "PRODUCT_LEVEL_APPLICABILITY_ONLY")]
            expl = [r for r in cited if r["automated_status"] == "EXPLICIT_OS_STATEMENT_FOUND"]
            if expl:
                disp, why = "EXPLICIT_OS_STATEMENT_FOUND", "official page states the Windows releases and (where present) event schema versions"
            elif ok:
                disp, why = "PRODUCT_LEVEL_APPLICABILITY_ONLY", "official page states a product-level scope, not an OS/build range"
            elif any(r["event_id_in_page"] for r in cited):
                disp, why = "NO_APPLICABILITY_STATEMENT", "page names the Event ID but states no applicability"
            else:
                disp, why = "SOURCE_DOES_NOT_NAME_EVENT_ID", "none of the cited pages names the Event ID in an event-like context"
        elif cand:
            disp, why = "CANDIDATE_SOURCE_NEEDS_HUMAN_REVIEW", f"{len(cand)} Microsoft Learn page(s) name the Event ID and the provider; not adopted"
        else:
            wd = win_disp.get((rec["event_id"], rec["provider"]), {})
            disp, why = "NO_DIRECT_SOURCE_FOUND", f"no strong candidate in this run; earlier disposition: {wd.get('disposition', 'n/a')}"
        dispositions.append({"record_key": key, "event_id": rec["event_id"], "provider": rec["provider"], "ledger_disposition": disp, "reason": why,
                             "cited_sources": len(cited), "strong_candidates": len(cand), "search_candidates_checked_no_match": sorted(set(checked.get(key, []))),
                             "human_status": "NEEDS_HUMAN_REVIEW" if disp != "NO_DIRECT_SOURCE_FOUND" else "UNVERIFIED"})
    return {"schema_version": 1, "generated_at": now, "note": ("Verbatim statements extracted from official Microsoft pages. "
            "Nothing is source-verified or reviewed; OS version, build, event schema version and documentation publication data are kept apart."),
            "summary": {"ledger_rows": len(rows), "records": len(dispositions),
                        "by_disposition": dict(sorted(Counter(d["ledger_disposition"] for d in dispositions).items())),
                        "by_row_status": dict(sorted(Counter(r["automated_status"] for r in rows).items()))},
            "dispositions": dispositions, "rows": rows}


def urlparse_host(url: str) -> str:
    return urllib.parse.urlparse(url).hostname or ""


def _safe(url: str, cache: Path):
    try:
        return parse_page(_fetch(url, cache))
    except Exception:  # noqa: BLE001 - recorded as FETCH_FAILED
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=CERT)
    args = parser.parse_args(argv)
    ledger = build(args.cache)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "windows_source_research_ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cols = list(ledger["rows"][0].keys())
    with (args.output_dir / "windows_source_research_ledger.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in ledger["rows"]:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()})
    print(json.dumps(ledger["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
