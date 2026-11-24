"""Collect REAL PostgreSQL state output for the class-D evaluators and record run-bound evidence.

Runs only against a disposable primary/standby pair that you provision yourself (see docs/acceptance/certification/
technical_evidence_report.md). Safety guards, all enforced before any statement is run:
  * host must be 127.0.0.1 / localhost,
  * database must be ``eims_cert_state``,
  * ``SHOW cluster_name`` must equal ``eims-cert-disposable`` on the primary (set at container start),
  * the operational EIMS database name is refused.
Actual ``pg_replication_slots`` / ``pg_stat_replication`` rows are stored next to the evaluator output; the expectation is
derived from the PostgreSQL documentation mapping (not from the evaluator) so the check is independent of the code under test.
Credentials come from environment variables and are never written to the evidence file.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUT = ROOT / "docs" / "acceptance" / "certification" / "technical_evidence_pg_state.json"
SLOT_KEY = "candidate:postgresql:replication:slot-retains-wal-filling-pg-wal"
LAG_KEY = "candidate:postgresql:replication:standby-lag-measurement"
# Documented meaning of wal_status (PostgreSQL 16 pg_replication_slots), mapped independently of the evaluator.
DOC_STATE = {"reserved": "within_max_wal_size", "extended": "retaining_beyond_max_wal_size",
             "unreserved": "at_risk_of_wal_removal", "lost": "lost"}


def _guard(dsn: str, role: str) -> None:
    parts = urlsplit(dsn)
    if parts.hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit(f"refusing {role}: host must be local")
    if (parts.path or "").lstrip("/") != "eims_cert_state":
        raise SystemExit(f"refusing {role}: database must be eims_cert_state")


def _seconds(value):
    return value.total_seconds() if isinstance(value, timedelta) else value


def _row(record) -> dict:
    return {k: (_seconds(v) if isinstance(v, timedelta) else (str(v) if k.endswith("lsn") else v)) for k, v in dict(record).items()}


async def _slot_rows(conn) -> dict:
    rows = await conn.fetch("select slot_name, active, wal_status, safe_wal_size, restart_lsn from pg_replication_slots")
    return {r["slot_name"]: _row(r) for r in rows}


async def collect(primary_dsn: str, standby_dsn: str, hashes: dict[str, str]) -> dict:
    import asyncpg
    from backend.domain.analyzer.services import state_diagnostics as sd

    _guard(primary_dsn, "primary")
    _guard(standby_dsn, "standby")
    p = await asyncpg.connect(primary_dsn)
    st = await asyncpg.connect(standby_dsn)
    cases: list[dict] = []
    try:
        if await p.fetchval("show cluster_name") != "eims-cert-disposable":
            raise SystemExit("refusing: primary is not marked as the disposable certification cluster")
        if not await st.fetchval("select pg_is_in_recovery()"):
            raise SystemExit("refusing: standby is not in recovery")
        env = {"server_version": await p.fetchval("show server_version"), "max_wal_size": await p.fetchval("show max_wal_size"),
               "max_slot_wal_keep_size": await p.fetchval("show max_slot_wal_keep_size"), "wal_keep_size": await p.fetchval("show wal_keep_size"),
               "host_os": platform.platform(), "topology": "1 primary + 1 streaming standby, physical slot for the standby, 1 orphan slot"}

        def add(key, polarity, why, row, expected, actual, passed, extra=None):
            cases.append({"record_key": key, "kind": "evaluator_real_state", "polarity": polarity, "why": why,
                          "actual_row": row, "expected": expected, "actual": actual, "passed": bool(passed), **(extra or {})})

        # ---- slot evaluator: healthy active standby slot (negative) -------------------------------------------------
        healthy = (await _slot_rows(p))["cert_standby_slot"]
        res = sd.evaluate_replication_slot(healthy)
        exp = {"state": DOC_STATE.get(healthy["wal_status"]), "attention": False}
        ok = healthy["wal_status"] == "reserved" and healthy["active"] is True
        add(SLOT_KEY, "negative", "real active, reserved standby slot must not raise attention", healthy, exp,
            {"state": res["state"], "attention": res["attention"]}, ok and {"state": res["state"], "attention": res["attention"]} == exp)

        # ---- slot evaluator: orphan slot while WAL accumulates (positive for every observed status) ----------------
        await p.execute("select pg_create_physical_replication_slot('cert_orphan', true)")
        await p.execute("create table if not exists cert_wal_filler(id serial primary key, pad text)")
        seen: dict[str, dict] = {}
        trajectory = []
        for i in range(24):
            await p.execute("insert into cert_wal_filler(pad) select repeat(md5(random()::text), 200000/32) from generate_series(1, 30)")
            await p.execute("select pg_switch_wal()")
            await p.execute("checkpoint")
            row = (await _slot_rows(p)).get("cert_orphan")
            if row is None:
                break
            trajectory.append({"iteration": i, "wal_status": row["wal_status"], "safe_wal_size": row["safe_wal_size"]})
            if row["wal_status"] and row["wal_status"] not in seen:
                seen[row["wal_status"]] = row
            if row["wal_status"] == "lost":
                break
        for status, row in seen.items():
            res = sd.evaluate_replication_slot(row)
            expected_attention = status != "reserved" or row["active"] is False
            exp = {"state": DOC_STATE[status], "attention": expected_attention}
            add(SLOT_KEY, "positive", f"real orphan slot observed with wal_status={status}", row, exp,
                {"state": res["state"], "attention": res["attention"]}, {"state": res["state"], "attention": res["attention"]} == exp)

        # ---- safe_wal_size NULL when max_slot_wal_keep_size = -1 (documented) --------------------------------------
        await p.execute("alter system set max_slot_wal_keep_size = -1")
        await p.execute("select pg_reload_conf()")
        await asyncio.sleep(1.5)
        unlimited = (await _slot_rows(p))["cert_standby_slot"]
        res = sd.evaluate_replication_slot(unlimited)
        text = " ".join(res["observations"] + res["false_positive_risks"])
        ok = unlimited["safe_wal_size"] is None and "max_slot_wal_keep_size is -1" in text
        add(SLOT_KEY, "positive", "real row with max_slot_wal_keep_size=-1: safe_wal_size is NULL and the evaluator explains it", unlimited,
            {"safe_wal_size": None, "explains_unlimited": True}, {"safe_wal_size": unlimited["safe_wal_size"], "explains_unlimited": "max_slot_wal_keep_size is -1" in text}, ok)
        await p.execute("alter system set max_slot_wal_keep_size = '64MB'")
        await p.execute("select pg_reload_conf()")

        # ---- lag evaluator -----------------------------------------------------------------------------------------
        async def lag_row():
            r = await p.fetchrow("select application_name, state, write_lag, flush_lag, replay_lag from pg_stat_replication where application_name like 'eims-cert%'")
            return _row(r) if r else None

        idle = None
        for _ in range(40):
            idle = await lag_row()
            if idle and all(idle[k] is None for k in ("write_lag", "flush_lag", "replay_lag")):
                break
            await asyncio.sleep(1)
        res = sd.evaluate_standby_lag(idle or {})
        ok = bool(idle) and all(idle[k] is None for k in ("write_lag", "flush_lag", "replay_lag")) and res["state"] == "no_lag_measurement" and res["attention"] is False
        add(LAG_KEY, "negative", "real caught-up idle standby: all lag columns NULL (documented) must not be read as failure", idle,
            {"state": "no_lag_measurement", "attention": False}, {"state": res["state"], "attention": res["attention"]}, ok)

        measured = None
        for _ in range(12):
            await p.execute("insert into cert_wal_filler(pad) select repeat('x', 4000) from generate_series(1, 2000)")
            for _ in range(20):
                measured = await lag_row()
                if measured and any(measured[k] is not None for k in ("write_lag", "flush_lag", "replay_lag")):
                    break
                await asyncio.sleep(0.05)
            if measured and any(measured[k] is not None for k in ("write_lag", "flush_lag", "replay_lag")):
                break
        values = [measured[k] for k in ("write_lag", "flush_lag", "replay_lag") if measured and measured[k] is not None]
        if values:
            thr = {"replay_lag": 0.0, "flush_lag": 0.0, "write_lag": 0.0}
            res = sd.evaluate_standby_lag(measured, thresholds=thr)
            exp_state = "caller_threshold_exceeded" if any(v > 0.0 for v in values) else "lag_measured"
            add(LAG_KEY, "positive", "real row with measurable lag and a caller-supplied threshold of 0 s (threshold is the caller's, not documented)", measured,
                {"state": exp_state, "attention": exp_state == "caller_threshold_exceeded"}, {"state": res["state"], "attention": res["attention"]},
                res["state"] == exp_state and res["attention"] == (exp_state == "caller_threshold_exceeded"), {"thresholds": thr})
            res2 = sd.evaluate_standby_lag(measured)
            add(LAG_KEY, "negative", "same real row with no caller threshold: no attention (documentation gives no threshold)", measured,
                {"state": "lag_measured", "attention": False}, {"state": res2["state"], "attention": res2["attention"]},
                res2["state"] == "lag_measured" and res2["attention"] is False)

        # ---- replay paused on the standby: observe what pg_stat_replication really reports -------------------------
        await st.execute("select pg_wal_replay_pause()")
        await p.execute("insert into cert_wal_filler(pad) select repeat('y', 4000) from generate_series(1, 2000)")
        paused = None
        for _ in range(30):
            await asyncio.sleep(0.5)
            paused = await lag_row()
            if paused and paused["replay_lag"] is not None and paused["replay_lag"] > 1.0:
                break
        replay_gap = await p.fetchval("select pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) from pg_stat_replication where application_name like 'eims-cert%'")
        res = sd.evaluate_standby_lag(paused or {}, thresholds={"replay_lag": 1.0})
        row_ok = bool(paused) and paused.get("replay_lag") is not None
        exp_state = "caller_threshold_exceeded" if row_ok and paused["replay_lag"] > 1.0 else ("lag_measured" if row_ok else "no_lag_measurement")
        add(LAG_KEY, "positive" if row_ok else "negative", "standby replay paused while the primary writes; evaluator vs the row actually returned (replay_lsn gap recorded)", paused,
            {"state": exp_state}, {"state": res["state"]}, res["state"] == exp_state, {"replay_lsn_gap_bytes": int(replay_gap or 0), "thresholds": {"replay_lag": 1.0}})
        await st.execute("select pg_wal_replay_resume()")

        await p.execute("select pg_drop_replication_slot('cert_orphan')")
        trajectory_info = trajectory
    finally:
        await p.close()
        await st.close()
    return {
        "schema_version": 1, "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_head": "",
        "note": ("Evidence from a real disposable PostgreSQL primary+standby. Expectations come from the PostgreSQL documentation mapping, not from the "
                 "evaluator. Automated technical evidence only; not a certification or a human review."),
        "environment": env, "orphan_slot_trajectory": trajectory_info,
        "record_hashes": {k: hashes.get(k, "") for k in (SLOT_KEY, LAG_KEY)}, "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    primary, standby = os.environ.get("EIMS_CERT_PG_PRIMARY_DSN"), os.environ.get("EIMS_CERT_PG_STANDBY_DSN")
    if not primary or not standby:
        raise SystemExit("set EIMS_CERT_PG_PRIMARY_DSN and EIMS_CERT_PG_STANDBY_DSN (disposable instances only)")
    from tools.build_certification_register import build_register
    from tools.run_certification_matching import _git_head
    hashes = {row["record_key"]: row["content_hash"] for row in build_register()["records"]}
    result = asyncio.run(collect(primary, standby, hashes))
    result["git_head"] = _git_head()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    failed = [c for c in result["cases"] if not c["passed"]]
    print(json.dumps({"cases": len(result["cases"]), "failed": len(failed),
                      "observed_slot_statuses": sorted({c["actual_row"]["wal_status"] for c in result["cases"] if c["record_key"] == SLOT_KEY and c.get("actual_row") and c["actual_row"].get("wal_status")})}))
    for c in failed:
        print("FAILED", c["record_key"][-40:], c["polarity"], "|", c["why"][:70], "| expected", c["expected"], "| actual", c["actual"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
