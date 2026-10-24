"""Bounded, escaped offline source inspector for synthetic experiment artifacts."""
from html import escape


def source_context(files, ref, radius=2):
    if not 0 <= radius <= 5:
        raise ValueError("source context radius outside bounded policy")
    if ref["file"] not in files:
        return None
    lines = files[ref["file"]][1].splitlines()
    first = ref["line"]
    last = ref.get("end_line", first)
    if not 1 <= first <= last <= len(lines) or last - first > 20:
        return None
    return [{"line": n, "text": lines[n - 1], "highlight": first <= n <= last}
            for n in range(max(1, first - radius), min(len(lines), last + radius) + 1)]


def render(prediction, files):
    title = escape(prediction["case_id"])
    pieces = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
              "<meta name='viewport' content='width=device-width,initial-scale=1'>",
              "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
              "<title>EIMS isolated investigation</title><style>body{font:16px/1.6 system-ui;max-width:1050px;margin:32px auto;padding:0 20px;color:#172033;background:#f6f8fb}section,details{background:white;padding:18px;margin:16px 0;border:1px solid #cbd5e1;border-radius:8px}summary{cursor:pointer;font-weight:600}pre{overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}mark{background:#fff0ac}small{color:#526174}.warning{border-left:5px solid #dc8a16;padding-left:12px}a{color:#1455ac}</style>",
              f"<h1 id='finding'>EIMS: {title}</h1>",
              "<p class='warning'>Synthetic DRAFT. Offline isolated demo; no human accuracy certification, operational History database, live vector store or external model.</p>"]
    native = prediction.get("native_response", {})
    overview = native.get("solutionSummary", {}).get("overview", "No native overview available")
    terminal = prediction.get("semantics_v2", {}).get("explicit_terminal_outcome")
    terminal_status = terminal["status"] if terminal else "UNKNOWN"
    pieces += [f"<section><h2>Native investigation</h2><p>{escape(overview)}</p>",
               f"<p>Correlation: {escape(str(native.get('correlationConfidence','single file')))}; association does not prove causation.</p>",
               f"<p>Explicit terminal outcome: {escape(terminal_status)}</p></section>"]
    for c in prediction.get("claims", []):
        pieces.append(f"<details><summary>{escape(c['category'])} / {escape(c['evidence_type'])}: {escape(c['text'])}</summary>")
        pieces.append("<p>Semantic support: NOT REVIEWED. Possible causes remain hypotheses.</p>")
        if not c["evidence"]:
            pieces.append("<p>No exact supporting source reference supplied for this claim.</p>")
        for ref in c["evidence"]:
            pieces.append(f"<h3>{escape(ref['file'])}:{ref['line']}</h3>")
            context = source_context(files, ref)
            if context is None:
                pieces.append("<p class='warning'>Original source unavailable or span invalid. History may contain compacted text; neighboring lines cannot be reconstructed safely.</p>")
            else:
                pieces.append("<pre>")
                for row in context:
                    value = escape(f"{row['line']:>4} | {row['text']}")
                    pieces.append(("<mark>" + value + "</mark>" if row["highlight"] else value) + "\n")
                pieces.append("</pre>")
        pieces.append("<a href='#finding'>Back to finding</a></details>")
    pieces += ["<section id='history'><h2>Isolated History reconstruction</h2>",
               f"<p>JSON snapshot reload matches native response: {escape(str(prediction.get('isolated_history_roundtrip',False)))}</p>",
               "<p>This uses an isolated serialized memory record. It is not a PostgreSQL persistence or installed-dashboard/USB certification.</p></section></html>"]
    return "\n".join(pieces)
