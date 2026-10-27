"""Read-only Docker Compose security inventory; no Docker daemon required.

Development Compose findings are reported but do not fail CI. A future
secure profile can be gated with --mode secure. Never echo secret values.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


SECRET_KEY = re.compile(r"(?:PASSWORD|SECRET|TOKEN|API_KEY|AUTH_PASS)", re.I)
INLINE_DB_CREDENTIAL = re.compile(r"://[^:/\s]+:[^@/\s]+@")
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _environment(service: dict[str, Any]) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {str(key): str(value) for key, value in env.items() if value is not None}
    if isinstance(env, list):
        result = {}
        for entry in env:
            key, separator, value = str(entry).partition("=")
            if separator:
                result[key] = value
        return result
    return {}


def _published_to_nonloopback(port: Any) -> bool:
    if isinstance(port, dict):
        return str(port.get("host_ip", "")).strip("[]") not in LOOPBACK
    # Compose short syntax: [HOST_IP:]HOST_PORT:CONTAINER_PORT[/protocol]
    segments = str(port).split("/")[0].rsplit(":", 2)
    if len(segments) < 3:
        return True
    return segments[0].strip("[]") not in LOOPBACK


def audit_compose(document: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        raise ValueError("Compose document must contain a services mapping")

    findings: list[dict[str, str]] = []

    def add(service: str, rule: str, severity: str, detail: str) -> None:
        findings.append({
            "service": service, "rule": rule,
            "severity": severity, "detail": detail,
        })

    for name, service in sorted(document["services"].items()):
        if not isinstance(service, dict):
            continue
        image = str(service.get("image") or "")
        if image and "@sha256:" not in image and (
            image.endswith(":latest") or (":" not in image.rsplit("/", 1)[-1])
        ):
            add(name, "IMAGE_UNPINNED", "medium", "Image uses latest or an implicit tag")

        for port in service.get("ports") or []:
            if _published_to_nonloopback(port):
                add(name, "NON_LOOPBACK_PORT", "high",
                    "Port is published without an explicit loopback host binding")

        env = _environment(service)
        for key, value in sorted(env.items()):
            if key.endswith("_FILE"):
                continue
            if SECRET_KEY.search(key) and value and "${" not in value and not value.startswith("$"):
                add(name, "INLINE_SECRET", "high",
                    f"Credential-like variable {key} has a literal value")
            if INLINE_DB_CREDENTIAL.search(value) and "${" not in value:
                add(name, "INLINE_URL_CREDENTIAL", "high",
                    f"Variable {key} contains an inline URL credential")

        command = service.get("command") or ""
        command_text = " ".join(map(str, command)) if isinstance(command, list) else str(command)
        if name.startswith("redis") or image.startswith("redis:"):
            if "--aclfile" not in command_text and "--requirepass" not in command_text:
                add(name, "REDIS_AUTH_UNVERIFIED", "high",
                    "No Redis ACL file or requirepass is visible in service command")

        entrypoint = service.get("entrypoint") or ""
        entrypoint_text = " ".join(map(str, entrypoint)) if isinstance(entrypoint, list) else str(entrypoint)
        if re.search(r"\bmc\s+anonymous\s+set\s+public\b", entrypoint_text, re.I):
            add(name, "PUBLIC_OBJECT_BUCKET", "high",
                "MinIO setup grants anonymous public bucket access")

        if env.get("AUTH_TYPE", "").lower() == "plain":
            add(name, "PGBOUNCER_PLAIN_AUTH", "medium",
                "PgBouncer uses plain authentication; review transport and policy")

    return sorted(findings, key=lambda f: (f["service"], f["rule"], f["detail"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", default="docker-compose.yml")
    parser.add_argument("--mode", choices=("dev", "secure"), default="dev")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    document = yaml.safe_load(Path(args.compose).read_text(encoding="utf-8"))
    findings = audit_compose(document)
    report = {
        "mode": args.mode,
        "compose": args.compose,
        "finding_count": len(findings),
        "findings": findings,
        "note": "Static source review only; no claim of deployed exposure.",
    }
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 1 if args.mode == "secure" and any(f["severity"] == "high" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
