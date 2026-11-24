"""Rebuild backend/domain/analyzer/services/vendor_reference_catalog.json from official pages.

Only definition tables whose rows can be copied verbatim by a deterministic parse are
generated here (PostgreSQL SQLSTATE appendix, systemd exit-status tables). Nothing is
inferred: code and name come from the page; descriptions are the vendor text.
Records are Reference Knowledge, source_referenced, never verified/validated/approved.
"""
import html
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend/domain/analyzer/services/vendor_reference_catalog.json"
PG_URL = "https://www.postgresql.org/docs/16/errcodes-appendix.html"
SD_URL = "https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html"
HOW = ("Scripted fetch and deterministic table parse; code, name and description copied from the "
       "page. Human re-read pending; not verified, validated or approved.")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def text(fragment):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def postgres(today):
    page = fetch(PG_URL)
    records, cls_code, cls_name = [], None, None
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = [text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [c for c in cells if c]
        if len(cells) == 1:
            m = re.match(r"Class (\w\w)\W+(.*)", cells[0])
            if m:
                cls_code, cls_name = m.group(1), m.group(2).strip()
            continue
        if len(cells) >= 2 and re.fullmatch(r"[0-9A-Z]{5}", cells[0]) and cls_code:
            code, name = cells[0], cells[1]
            records.append({
                "reference_id": f"postgresql:sqlstate:{code}",
                "vendor": "PostgreSQL Global Development Group", "product": "PostgreSQL",
                "product_family": "PostgreSQL", "version_scope": "PostgreSQL 16 documentation; applicability to other majors not checked",
                "code_type": "sqlstate", "code": code, "name": name,
                "category": f"Class {cls_code} - {cls_name}", "domain": "database",
                "description": f"PostgreSQL Appendix A lists SQLSTATE {code} with condition name {name} (class {cls_code}, {cls_name}).",
                "source": {"title": "PostgreSQL 16 Documentation, Appendix A. PostgreSQL Error Codes", "url": PG_URL,
                           "type": "vendor_documentation", "retrieved": today, "method": HOW},
            })
    return records


def systemd(today):
    page = fetch(SD_URL)
    start = page.find("Process Exit Codes")
    seg = page[start:start + 40000]
    records = []
    for row in re.findall(r"<tr>(.*?)</tr>", seg, re.S):
        cells = [text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) == 3 and cells[0].isdigit() and cells[1].startswith("EXIT_"):
            code, name, desc = cells
            records.append({
                "reference_id": f"systemd:exit_status:{code}",
                "vendor": "systemd project", "product": "systemd",
                "product_family": "Linux service manager", "version_scope": "systemd.exec man page (latest at retrieval); distribution package versions not checked",
                "code_type": "process_exit_status", "code": code, "name": name,
                "category": "Process exit codes (service start)", "domain": "linux_service",
                "description": f"systemd.exec documents exit status {code} ({name}): {desc}",
                "source": {"title": "systemd.exec(5), Process Exit Codes", "url": SD_URL,
                           "type": "vendor_documentation", "retrieved": today, "method": HOW},
            })
    return records


KAFKA_URL = "https://kafka.apache.org/41/design/protocol/"
IANA_URL = "https://www.iana.org/assignments/http-status-codes/http-status-codes-1.csv"
ERRNO_URL = "https://man7.org/linux/man-pages/man3/errno.3.html"
HAPROXY_URL = "https://docs.haproxy.org/2.8/configuration.html"


def _rec(rid, vendor, product, family, scope, ctype, code, name, category, domain, desc, title, url, today, kind="vendor_documentation"):
    return {"reference_id": rid, "vendor": vendor, "product": product, "product_family": family,
            "version_scope": scope, "code_type": ctype, "code": code, "name": name, "category": category,
            "domain": domain, "description": desc,
            "source": {"title": title, "url": url, "type": kind, "retrieved": today, "method": HOW}}


def kafka(today):
    page = fetch(KAFKA_URL)
    i = page.find('id=error-codes')
    table = page[i:page.find("</table>", i)]
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        c = [text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(c) == 4 and re.fullmatch(r"-?\d+", c[1]) and c[0] != "NONE":
            name, code, retry, desc = c
            out.append(_rec(f"kafka:error_code:{code}", "Apache Software Foundation", "Apache Kafka", "Messaging",
                            "Kafka protocol documentation 4.1; broker/client version support per code not checked",
                            "protocol_error_code", code, name, "Protocol error codes", "messaging",
                            f"Kafka protocol documentation lists error code {code} ({name}); retriable: {retry}. {desc}".strip(),
                            "Apache Kafka protocol, Error Codes", KAFKA_URL, today))
    return out


def iana_http(today):
    import csv, io
    rows = csv.DictReader(io.StringIO(fetch(IANA_URL)))
    out = []
    for r in rows:
        code, desc = r["Value"].strip(), r["Description"].strip()
        if not re.fullmatch(r"\d{3}", code) or desc.lower() in ("unassigned", "(unused)"):
            continue
        out.append(_rec(f"http:status_code:{code}", "IANA", "HTTP status code registry", "Web / HTTP",
                        "IANA registry as retrieved; applies to any HTTP server or proxy, product-specific behavior not covered",
                        "http_status", code, desc, "HTTP status codes", "web_middleware",
                        f"IANA HTTP Status Code Registry lists {code} as '{desc}' (reference: {r['Reference'].strip()}).",
                        "IANA Hypertext Transfer Protocol (HTTP) Status Code Registry", IANA_URL, today, "standards_registry"))
    return out


def errno_linux(today):
    page = text(fetch(ERRNO_URL))
    i = page.find("E2BIG Argument")
    j = page.find("The error numbers", i) if page.find("The error numbers", i) > 0 else page.find("NOTES", i)
    body = page[i:j if j > 0 else i + 12000]
    parts = re.split(r"(?:(?<=\s)|^)(E[A-Z0-9]{2,})\s(?=[A-Z])", body)
    out = []
    for k in range(1, len(parts) - 1, 2):
        name, desc = parts[k], parts[k + 1].strip()
        if not desc or len(desc) > 200:
            continue
        out.append(_rec(f"linux:errno:{name}", "Linux man-pages project", "Linux errno(3)", "Linux system calls",
                        "man7.org errno(3) as retrieved; kernel/glibc version and architecture-specific numbers not checked",
                        "errno_name", name, name, "Symbolic error names", "linux_os",
                        f"errno(3) lists {name}: {desc}", "errno(3) - Linux manual page", ERRNO_URL, today))
    return out


def haproxy(today):
    page = text(fetch(HAPROXY_URL))
    heads = [m.start() for m in re.finditer("Session state at disconnection TCP and HTTP logs", page)]
    seg = page[heads[-1]:heads[-1] + 16000]
    out = []
    for label, a, b in (("first", "On the first character", "on the second character"),
                        ("second", "on the second character", "the third character tells"),
                        ("third", "the third character tells", "the fourth character")):
        ia = seg.lower().find(a.lower()); ib = seg.lower().find(b.lower(), ia + 10)
        if ia >= 0 and ib < 0:
            ib = seg.find(" - the ", ia + 30)  # next numbered item when the manual has no explicit end marker
        if ia < 0 or ib < 0:
            continue
        chunk = seg[ia:ib]
        for m in re.finditer(r"(?:(?<=\s)|^)([A-Za-z\-]) : (.*?)(?= [A-Za-z\-] : |$)", chunk):
            ch, desc = m.group(1), re.sub(r"\s+-$", "", m.group(2).strip())
            out.append(_rec(f"haproxy:termination_state_{label}_char:{ch}", "HAProxy Technologies", "HAProxy", "Load balancer / proxy",
                            "HAProxy 2.8 configuration manual, 'Session state at disconnection'; other versions not compared",
                            f"termination_state_{label}_character", ch, f"termination_state {label} character '{ch}'",
                            "Log termination state", "web_middleware",
                            f"HAProxy documents termination_state {label} character '{ch}': {desc}",
                            "HAProxy 2.8 Configuration Manual, Session state at disconnection", HAPROXY_URL, today))
    return out


def main():
    today = date.today().isoformat()
    records = postgres(today) + systemd(today) + kafka(today) + iana_http(today) + errno_linux(today) + haproxy(today)
    for r in records:
        r.update(knowledge_class="reference_knowledge", evidence_maturity="source_referenced",
                 lifecycle_status="candidate", remediation=None,
                 remediation_status="none_in_source",
                 parser_mapping="missing_parser",
                 limitations="Definition only. The source gives no diagnosis or remediation; this record is not diagnostic guidance.")
        if r["product"] == "PostgreSQL":
            r.update(parser_mapping="parser_mapped",
                     parser_mapping_note="Resolved from a PostgreSQL jsonlog entry (documented keys error_severity, state_code, message plus a process/session key); class 00 (successful completion) is not surfaced. Other log formats are not parsed.")
        elif r["product"] == "systemd":
            r.update(parser_mapping="parser_mapped",
                     parser_mapping_note="Resolved from a systemd journal/syslog line '<kind> exited, code=exited, status=<N>/<NAME>' printed by systemd (src/core/unit.c); status 0 is not surfaced and signal terminations are not matched.")
    ids = [r["reference_id"] for r in records]
    assert len(ids) == len(set(ids)), "duplicate reference ids"
    doc = {"schema_version": 1, "generated_by": "tools/build_vendor_reference_inventory.py", "records": records}
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(records), "records", file=sys.stderr)


if __name__ == "__main__":
    main()
